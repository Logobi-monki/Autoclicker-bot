"""autoclicker.py

Refactorisé pour :
- Threading propre avec Events (start/pause/stop) pour éviter une boucle occupée.
- Hotkeys globales (F6 et Ctrl+Alt+S pour toggle) et Kill Switch (Esc) pour arrêt d'urgence.
- Intervalle configurable (0 pour clics aussi rapides que possible sans délai artificiel).
- Utilise pynput (Controller.press/release) pour réduire l'overhead par rapport à click().
- Code structuré en classe, commentaires en français.

Usage : lancer le script, appuyez sur F6 pour basculer l'autoclicker, Esc pour kill immédiat.
"""

import time
import threading
import sys
import logging
from pynput.mouse import Controller, Button
from pynput.keyboard import GlobalHotKeys

# Configuration (modifiable)
DEFAULT_INTERVAL = 0.0  # secondes entre les clics; 0.0 = aussi rapide que possible
DEFAULT_BUTTON = Button.left
TOGGLE_KEYS = '<f6>'  # raccourci principal pour activer / désactiver
ALT_TOGGLE_KEYS = '<ctrl>+<alt>+s'  # raccourci secondaire
KILL_KEYS = '<esc>'  # Kill switch d'urgence

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


class AutoClicker:
    """AutoClicker gérant un thread worker autonome.

    Méthodes publiques :
    - start() : démarre le thread worker (idempotent)
    - stop() : arrête proprement le thread et attend sa terminaison
    - toggle() : bascule entre pause / reprise
    - pause(), resume()
    - is_running : True si le clicker est en train de cliquer

    Implementation details:
    - _running : threading.Event indiquant que le clicker doit cliquer
    - _stop : threading.Event demandant l'arrêt complet du thread
    - Le worker utilise _stop.wait(timeout) pour attendre de façon efficace
      et permet un délai minimal quand interval == 0.
    """

    def __init__(self, interval: float = DEFAULT_INTERVAL, button: Button = DEFAULT_BUTTON):
        self.interval = max(0.0, float(interval))
        self.button = button
        self._mouse = Controller()

        self._running = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, name='AutoClickerThread', daemon=True)

    def start(self):
        """Démarre le thread worker si nécessaire."""
        if not self._thread.is_alive():
            logging.info('Démarrage du thread autoclicker (interval=%s s)', self.interval)
            self._thread.start()

    def _worker(self):
        """Boucle de clic qui respecte _running et _stop sans busy-waiting.

        Si interval == 0.0 on clique aussi vite que possible en laissant
        néanmoins le scheduler OS faire son boulot (time.sleep(0)).
        """
        next_wait = 0.0
        while not self._stop.is_set():
            if self._running.is_set():
                # Exécuter un clic
                self._perform_click()

                if self.interval > 0.0:
                    # Attend l'intervalle ou l'arrêt (_stop) si déclenché
                    if self._stop.wait(self.interval):
                        break
                else:
                    # Pas d'intervalle demandé : on cède le CPU brièvement pour éviter 100% CPU
                    # time.sleep(0) laisse le scheduler réordonnancer les threads rapidement
                    time.sleep(0)
            else:
                # En attente jusqu'à ce qu'on reprenne ou qu'on arrête
                # Polling très peu coûteux grâce à wait(timeout)
                if self._stop.wait(0.1):
                    break

        logging.info('Worker autoclicker arrêté')

    def _perform_click(self):
        """Effectue le clic de manière minimale (press/release) pour réduire l'overhead."""
        try:
            self._mouse.press(self.button)
            self._mouse.release(self.button)
        except Exception:
            logging.exception('Échec du clic')

    def toggle(self):
        """Bascule entre pause et reprise."""
        if self._running.is_set():
            self.pause()
        else:
            self.resume()

    def pause(self):
        """Met en pause le clic (ne termine pas le thread)."""
        if self._running.is_set():
            self._running.clear()
            logging.info('Autoclicker mis en pause')

    def resume(self):
        """Reprend le clic."""
        if not self._running.is_set():
            self._running.set()
            logging.info('Autoclicker en cours d\'exécution')

    def stop(self, join_timeout: float = 1.0):
        """Demande l'arrêt et attend la terminaison du thread."""
        logging.info('Arrêt demandé pour l\'autoclicker')
        self._stop.set()
        # Lever _running pour débloquer si on était en pause
        self._running.set()
        if self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

    @property
    def is_running(self) -> bool:
        return self._running.is_set()


def main():
    clicker = AutoClicker(interval=DEFAULT_INTERVAL, button=DEFAULT_BUTTON)
    clicker.start()

    # Fonctions de callback pour GlobalHotKeys
    def _toggle():
        clicker.toggle()

    def _kill():
        logging.warning('Kill switch détecté — arrêt immédiat')
        try:
            clicker.stop()
        finally:
            # forcer la sortie immédiate
            # os._exit est plus brutal mais garantit l'arrêt si quelque chose bloque
            import os

            os._exit(0)

    # Map des raccourcis
    hotkey_map = {
        TOGGLE_KEYS: _toggle,
        ALT_TOGGLE_KEYS: _toggle,
        KILL_KEYS: _kill,
    }

    logging.info('Raccourcis disponibles : %s (toggle), %s (toggle secondaire), %s (kill)',
                 TOGGLE_KEYS, ALT_TOGGLE_KEYS, KILL_KEYS)
    logging.info('Appuyez sur %s pour basculer, sur %s pour tuer le script', TOGGLE_KEYS, KILL_KEYS)

    # Listener global pour les hotkeys — tourne dans le thread du listener
    with GlobalHotKeys(hotkey_map) as h:
        try:
            h.join()
        except KeyboardInterrupt:
            logging.info('Interruption clavier détectée, arrêt propre...')
            clicker.stop()


if __name__ == '__main__':
    main()
