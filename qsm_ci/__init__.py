"""qsm-ci — command-line companion for the QSM-CI reconstruction challenge.

Scaffold a submission (`qsm-ci new`), run one stage on explicit input files and score it
(`qsm-ci run ... --truth`), and open a pull request (`qsm-ci submit`). The scorer is the exact
same code the challenge CI runs (`qsm_ci.qsm_eval`), so local numbers match the leaderboard.
"""

__version__ = "0.1.0"
