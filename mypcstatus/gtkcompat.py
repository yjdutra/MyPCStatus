"""Fixa as versoes do GObject Introspection antes de qualquer import.

Sem isso o gi escolhe a versao mais nova disponivel por namespace: o Zorin 18
tem GTK 3 e 4 lado a lado, entao `from gi.repository import Gdk` puxaria o
Gdk 4.0 e quebraria contra o Gtk 3.0. Todo modulo do app importa este aqui
ANTES de pedir qualquer coisa do gi.repository.
"""

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")

HAVE_NOTIFY = False
HAVE_INDICATOR = False

try:
    gi.require_version("Notify", "0.7")
    HAVE_NOTIFY = True
except ValueError:
    pass

try:
    gi.require_version("AppIndicator3", "0.1")
    HAVE_INDICATOR = True
except ValueError:
    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        HAVE_INDICATOR = True
    except ValueError:
        pass
