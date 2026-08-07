"""
conftest.py — fixtures compartilhados para os testes dos background jobs.
"""
import sys
import os

# Garante que o pacote `app` possa ser importado sem instalar o projeto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
