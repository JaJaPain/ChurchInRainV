"""
AVizualizer - Audio Visualizer for Modern Christian Rock Music
Entry point: launches the control panel UI.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ui.launcher import Launcher

if __name__ == "__main__":
    app = Launcher()
    app.run()
