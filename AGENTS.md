# OpenTrace BIM — guia para agentes (Claude, GPT)

Leia este arquivo primeiro. Ele substitui a leitura do projeto inteiro.

## Regras
- Plugin para IngeTrazo (testado no 0.5.8). Python + PySide6. Regras do host: `ingelibre/ingetrazo/docs/plugins.md`.
- Código, comentários e commits em inglês. Textos da interface em português passam por `i18n.t()`.
- Sem base64, sem binários no pacote, sem gambiarras (índices mágicos, try/except mudo, código morto).
- Toda mudança no modelo passa por um comando do histórico (Desfazer/Refazer).
- Nunca mexer em `main`, release ou catálogo. Trabalho em branch `claude/*` ou `gpt/*`.
- `ui.py` e `suite_panel.py` são compartilhados: um agente por vez.
- Pronto = testes do GitHub verdes + teste do Leandro no Windows.
- Toda entrega para teste vem com link direto de download do zip. O CI publica o link como anotação "Download do pacote de teste" do check; se não houver, anexe o zip na conversa.

## Mapa do código (OpenTrace_BIM/)
| Área | Arquivos |
|---|---|
| Entrada do plugin | `__init__.py` |
| Parede: modelo e malha | `model.py` (registro, validação, malha, vãos), `commands.py` |
| Parede: interface e edição de trajetória | `ui.py` (WallController), `path_edit.py`, `wall_tool.py`, `snaprefs.py` |
| Cache por versão do documento | `wall_cache.py` |
| Vãos na parede | `wall_face.py` (face como folha estação × altura), `wall_opening_edit.py` (ferramentas da laje adaptadas), `wall_opening_place.py` (colocar/desenhar), `wall_opening_ui.py` (seleção, radial, desenho), `wall_polygon.py` (geometria 2D pura) |
| Portas e janelas | `door_window_core.py` (puro), `door_window_commands.py`, `door_window_geometry.py` |
| Laje e vãos da laje (referência de edição) | `slab_model.py`, `slab_edit.py`, `slab_opening_edit.py`, `slab_ui.py` |
| Pilar, viga, perfis | `column_*`, `beam_*`, `structure_edit.py`, `profile_editor.py` |
| Interface geral | `contextual_bar.py` (barra de opções), `suite_panel.py` (paleta lateral), `palette.py` (radial), `icons.py`, `help_dialog.py` |
| BIM / IFC | `bim.py`, `bim_ui.py`, `ifc_export.py`, `ifc_import.py` |

## Testes
- `tests/`: Python puro. `tests_host/`: com IngeTrazo real, Qt offscreen.
- CI: `.github/workflows/claude-branches.yml` (branches `claude/**`), inclui benchmark e zip de teste.
- Falhas aparecem como anotações do check (sem precisar abrir o log).

## Decisões vigentes (12/10/2026)
- Topo: fileira de ferramentas (recolhível) + barra de opções da ferramenta ativa (como o Info Box do Archicad). A barra não troca ferramenta.
- Paleta lateral: plantas, vistas, BIM/IFC, Projeto; por enquanto também as configurações completas da ferramenta/objeto.
- Vãos: contorno na face da parede, editado com o motor da abertura da laje; ficam presos à parede onde nasceram.
- Pontos de controle: só nos vértices; arestas são linhas (sem bolinha no meio).

## Estado e próximos passos
Ver `docs/NEXT.md`.
