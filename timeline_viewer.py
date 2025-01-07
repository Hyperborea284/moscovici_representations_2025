import wx
import os
import sys
from flask import jsonify

# Ajustar os caminhos para a estrutura do projeto
def make_sure_timelinelib_can_be_imported():
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "timeline-2.9.0", "source"))
    sys.path.insert(0, base_path)

def install_gettext_in_builtin_namespace():
    def _(message):
        return message
    import builtins
    if not "_" in builtins.__dict__:
        builtins.__dict__["_"] = _

# Garantir que a biblioteca timelinelib possa ser importada
make_sure_timelinelib_can_be_imported()
install_gettext_in_builtin_namespace()

from timelinelib.db import db_open
from timelinelib.canvas import TimelineCanvas

class TimelineViewerApp(wx.App):
    def __init__(self, timeline_file, *args, **kwargs):
        self.timeline_file = timeline_file
        super().__init__(*args, **kwargs)

    def OnInit(self):
        frame = TimelineViewerFrame(None, "Visualizador de Timeline", self.timeline_file)
        frame.Show()
        return True

class TimelineViewerFrame(wx.Frame):
    def __init__(self, parent, title, timeline_file):
        super().__init__(parent, title=title, size=(800, 400))
        self.timeline_file = timeline_file

        # Configuração da interface
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Canvas da Timeline
        self.canvas = TimelineCanvas(panel)
        sizer.Add(self.canvas, 1, wx.EXPAND)

        panel.SetSizer(sizer)
        self._display_timeline()

    def _display_timeline(self):
        # Carregar e exibir a timeline no canvas
        try:
            db = db_open(self.timeline_file)
            db.display_in_canvas(self.canvas)
        except Exception as e:
            wx.MessageBox(f"Erro ao carregar a timeline: {e}", "Erro", wx.ICON_ERROR)

    def render_html(self):
        """
        Renderiza a timeline para ser exibida como HTML em um container na aba Timeline.
        """
        try:
            # Renderizando o canvas para HTML
            html_output = "<div id='timelineContainer'>" + self.canvas.RenderAsHTML() + "</div>"
            return html_output
        except Exception as e:
            return jsonify({"error": f"Erro ao renderizar a timeline: {e}"})

def start_timeline_viewer(timeline_file):
    """
    Função para iniciar o visualizador de timeline. 
    Deve ser chamada pela aplicação Flask quando a aba Timeline é ativada.

    :param timeline_file: Caminho para o arquivo de timeline a ser exibido.
    """
    app = TimelineViewerApp(timeline_file)
    app.MainLoop()
