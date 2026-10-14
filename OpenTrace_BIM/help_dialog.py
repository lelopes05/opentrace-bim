# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenTrace BIM local help. Text/vector instructions, no stale screenshots."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget,
)

from . import __version__


class HelpDialog(QDialog):
    """Tool-aware manual with 'O que há de novo' as its first chapter."""

    CHAPTERS=(
        ("new", "O que há de novo"),
        ("overview", "Visão geral"),
        ("wall", "Paredes"),
        ("slab", "Lajes"),
        ("opening", "Aberturas, portas e janelas"),
        ("column", "Pilares e vigas"),
        ("arrange", "Alinhar e distribuir"),
        ("project", "Projeto e IFC"),
        ("about", "Sobre o OpenTrace BIM"),
    )
    CONTENT={
        "new": """<h2>O que há de novo nesta compilação experimental</h2>
        <p>A interface do OpenTrace BIM está sendo reorganizada em uma
        <b>barra contextual por ferramenta ou seleção</b> e uma
        <b>paleta lateral de edição BIM</b>. Os controles rápidos acessam os
        mesmos campos de propriedades do editor, sem criar outro modelo.</p>
        <p>Esta é uma compilação experimental do PR #8. A implementação deve
        ser conferida visualmente no IngeTrazo para Windows antes da aprovação.</p>
        <p>Os editores de arestas/vértices continuam na viewport e na paleta
        contextual. A barra superior não substitui essa edição.</p>""",
        "overview": """<h2>Três áreas, uma única geometria</h2>
        <p><b>Faixa superior:</b> selecione como construir e ajuste medidas,
        referência e níveis mais utilizados. A faixa muda com a ferramenta.</p>
        <p><b>Paleta lateral:</b> biblioteca, materiais, camadas e propriedades
        completas dos objetos. Os grupos podem ser recolhidos.</p>
        <p><b>Viewport e paleta radial:</b> selecionar, arrastar hotspots,
        editar vértices e arestas. Use os comandos nativos do IngeTrazo para
        desfazer e refazer.</p>
        <p>A seleção de um objeto existente não deve iniciar a criação de outro.</p>""",
        "wall": """<h2>Paredes</h2>
        <p>Ative <b>Parede</b>. Escolha reta, retângulo por diagonal ou por
        base e largura. A ferramenta de parede curva disponibiliza arco
        normal, por centro e por três pontos.</p>
        <p>Escolha alinhamento exterior/central/interior, estrutura simples
        ou composta e configure espessura, altura e vínculos de níveis.
        Em parede composta a espessura resulta das camadas.</p>
        <p>Para editar uma parede pronta, selecione-a; geometria detalhada,
        edição da referência e perfis permanecem nos editores próprios.</p>""",
        "slab": """<h2>Lajes</h2>
        <p>Ative <b>Laje</b>, escolha retângulo por diagonal, base + largura
        ou polígono. Ajuste nível, offset, espessura e composição.</p>
        <p>Para editar aberturas de laje, selecione os pontos/arestas do
        contorno e use a paleta radial própria. Não confunda os métodos de
        criação com as ferramentas de edição posteriores.</p>""",
        "opening": """<h2>Aberturas e esquadrias</h2>
        <p><b>Abertura</b> cria um vão livre retangular ou poligonal hospedado
        na parede. A ferramenta pode adquirir sua parede no clique seguinte.</p>
        <p><b>Porta e janela</b> possuem inserção hospedada e ancoragem
        esquerda/centro/direita; portas permitem inverter o giro.</p>
        <p>Selecione o vão ou uma esquadria para editar sua largura,
        altura, peitoril ou posição. Para contornos poligonais, use os
        vértices/arestas e seus comandos específicos na paleta.</p>
        <p>O teste completo de reedição e arraste deve ser feito no Windows;
        um teste automatizado não certifica a sensação do mouse na viewport.</p>""",
        "column": """<h2>Pilares e vigas</h2>
        <p>Abra a ferramenta de <b>Pilar</b> ou <b>Viga</b> na paleta.
        As seções simples e perfis disponíveis são controlados pelos
        editores próprios. Posições e alterações geométricas complexas são
        realizadas nos pontos de edição do modelo.</p>
        <p>Opções futuras aparecem somente quando têm motor implementado.</p>""",
        "arrange": """<h2>Alinhar e distribuir</h2>
        <p>Selecione pelo menos <b>dois objetos completos</b> para alinhar
        pelo início, centro ou fim nos eixos globais X, Y ou Z.</p>
        <p>Para distribuir espaços livres iguais, selecione
        <b>três ou mais objetos</b>; os extremos são mantidos. A operação
        completa é desfeita em um único comando.</p>
        <p>Esta versão não manipula faces ou arestas soltas.</p>""",
        "project": """<h2>Informações do Projeto e BIM/IFC</h2>
        <p>Use o botão <b>ⓘ</b> para cadastrar nome, cliente, localização,
        responsáveis, terreno e edifício sem recriar o modelo.</p>
        <p>Os dados IFC, opções de importar/exportar e propriedades BIM dos
        elementos ficam na aba própria. Os níveis existentes do IngeTrazo
        são reutilizados, não replicados em um cadastro paralelo.</p>""",
        "about": """<h2>OpenTrace BIM</h2>
        <p>Extensão livre para modelagem arquitetônica paramétrica no
        IngeTrazo. Licenciamento: <b>GPL-3.0-or-later</b>.</p>
        <p>Repositório e histórico de desenvolvimento:
        <a href="https://github.com/lelopes05/opentrace-bim">
        github.com/lelopes05/opentrace-bim</a>.</p>
        <p>O OpenTrace BIM consulta o catálogo oficial para avisar quando há
        versão nova, se essa opção estiver ligada na paleta. A consulta é
        somente informativa: para atualizar, abra
        <b>Extensions ▸ Manage extensions</b> no IngeTrazo.
        O plugin não baixa, instala nem substitui arquivos.</p>""",
    }

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName("opentrace_help_dialog")
        self.setWindowTitle("OpenTrace BIM — Manual e Sobre")
        self.resize(800,570)
        self.setMinimumSize(QSize(550,380))
        root=QVBoxLayout(self)
        root.setContentsMargins(12,12,12,12)
        root.setSpacing(8)
        heading=QLabel("OpenTrace BIM  ·  Manual",self)
        heading.setStyleSheet("font-size:15pt;font-weight:700;")
        root.addWidget(heading)
        bar=QHBoxLayout()
        bar.setSpacing(10)
        self.chapters=QListWidget(self)
        self.chapters.setObjectName("opentrace_help_chapters")
        self.chapters.setFixedWidth(210)
        for key,label in self.CHAPTERS:
            self.chapters.addItem(label)
        bar.addWidget(self.chapters)
        self.article=QTextBrowser(self)
        self.article.setObjectName("opentrace_help_article")
        self.article.setOpenExternalLinks(True)
        bar.addWidget(self.article,1)
        root.addLayout(bar,1)
        footer=QHBoxLayout()
        footer.addWidget(QLabel(f"OpenTrace BIM {__version__} · GPL-3.0-or-later"))
        footer.addStretch(1)
        close=QPushButton("Fechar",self)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)
        self.chapters.currentRowChanged.connect(self._show_chapter)
        self.chapters.setCurrentRow(0)

    def _show_chapter(self,row):
        if row<0:return
        key=self.CHAPTERS[row][0]
        self.article.setHtml(self.CONTENT[key])

    def show_for_context(self,context=None):
        context={
            "wall_edit":"wall",
            "slab_edit":"slab","opening_edit":"opening",
            "polygon_edit":"opening","door":"opening","window":"opening",
            "beam":"column","bim":"project",
        }.get(context,context)
        keys=[k for k,_ in self.CHAPTERS]
        self.chapters.setCurrentRow(keys.index(context) if context in keys else 0)
        self.show()
        self.raise_()
