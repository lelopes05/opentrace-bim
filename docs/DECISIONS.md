# Decisões

Só o que vale hoje. A data é de quando foi decidido. Onde este arquivo conflitar com `AGENTS.md`, vale o `AGENTS.md`.
O histórico dos cadernos antigos (`INTERFACE_MASTER.md` e `DEVELOPMENT_MASTER.md`, removidos em 13/10/2026) fica no git.

## Aprovado

### Interface
- 13/10: fileira e barra de opções são painéis flutuantes sobre a vista, no canto superior esquerdo, como o ArchXQ; não são toolbars do host.
- 12/10: topo com fileira de ferramentas recolhível e, abaixo, a barra de opções da ferramenta ativa (como o Info Box do Archicad). A barra mostra e edita opções; não troca de ferramenta.
- 09/10: a barra é uma faixa única, recolhível e baixa; o menu nativo do IngeTrazo continua como está.
- 09/10: cada propriedade tem uma só fonte de verdade, o campo do controlador. A barra e a paleta espelham esse campo; editar num atualiza o outro.
- 09/10: modos construtivos em ícones com dica ao passar o mouse e título pequeno. Só aparece modo que funciona.
- 12/10: a paleta lateral tem plantas, vistas, BIM/IFC e Projeto; por enquanto também as configurações completas da ferramenta ou objeto. Edição de vértice e aresta fica na viewport (radial) e na paleta, nunca na barra.
- 09/10: marca visível "OpenTrace BIM"; textos da interface em português, por `i18n.t()`.
- 09/10: "Informações do Projeto" (ⓘ) abre uma página na própria paleta e usa o cadastro BIM existente, acrescido de cliente e localização. Os níveis vêm do IngeTrazo; não há outro gerenciador de níveis.
- 09/10: Alinhar e distribuir em X, Y e Z (↔): início, centro ou fim; espaço livre igual com pelo menos três objetos; só grupos completos; um comando desfazível.
- 09/10: ajuda "?" em capítulos, sempre começando por "O que há de novo"; "Sobre" só com links reais (repositório, licença, discussão #449 do IngeTrazo). Texto e desenhos, sem capturas de tela que envelhecem.
- 11/10: CI verde e Qt offscreen não aprovam interface. O aceite visual é o teste do Leandro no Windows.

- 13/10: ferramentas só pela fileira do topo e pelo menu; barra e paleta nunca trocam de ferramenta. Sem atalhos de teclado para as ferramentas.
- 13/10: toda ferramenta e toda função de edição continuam na última escolha da sessão (forma, medidas, âncora, função do radial) até o usuário escolher outra.
- 13/10: medidas são do objeto. A ferramenta lembra as últimas da sessão; editar um objeto não muda a ferramenta nem os outros objetos (sem família ou biblioteca para cada variação).
- 13/10: fileira com Parede, Laje, Pilar, Viga, Abertura, Porta, Janela e Perfil complexo; Membrana entra quando estiver pronta.
- 13/10: Home da paleta já prevê Plantas e Vistas, escondidas até existirem.
- 13/10: parede reta e curva são geometrias da ferramenta Parede, escolhidas na barra (como o Archicad), não ferramentas separadas.
- 13/10: a fileira de ferramentas recolhe para uma versão compacta só com ícones; não some. Normal: ícone com nome ao lado.
- 13/10: cor de destaque: petróleo na ferramenta ativa, laranja na opção marcada e na seção aberta da paleta.

### Vãos
- 12/10: o vão é um contorno na face da parede, editado com o motor da abertura da laje, e fica preso à parede onde nasceu.
- 12/10: pontos de controle só nos vértices, desenhados como bolas. A aresta é uma linha clicável. O radial de aresta usa o meio da aresta como âncora, sem desenhar nada ali.
- 10/10: recuar a parede não apaga o vão. Registro, ID e GUID IFC ficam mesmo com o vão fora do trecho; só a parte que cabe corta a malha.
- 10/10: vão retangular livre vira polígono ao confirmar a primeira edição de vértice ou aresta (um comando; o Desfazer devolve o retângulo). Porta e janela nunca viram polígono sozinhas.
- 09/10: porta e janela são grupos 3D separados da parede, ligados ao vão por `source_id`. A porta aceita `sill=0`; porta mais alta que a parede baixa não apaga a parede.
- 09/10: a porta tem três âncoras (esquerda, centro, direita) e um único comando para inverter o giro.

### Entrega
- 10/10: pacote de teste = um ZIP só, com a pasta `OpenTrace_BIM/` na raiz, sem ZIP dentro de ZIP.
- 09/10: nada vai para `main`, release ou catálogo sem autorização expressa; o release público segue em 0.12.9.

## Descartado
- 11/10: faixa em linha própria abaixo dos menus; descartada em 13/10 porque o IngeTrazo reaplica restoreState e _pack_toolbars e desloca toolbars desconhecidas para a mesma linha.
- 09/10: Ribbon fixo com famílias de ícones sempre expostas.
- 09/10: segunda ou terceira barra permanente; edição de vértice, aresta ou propriedade avançada dentro da barra.
- 10/10: bolinha no meio das arestas (substituída em 12/10 pela aresta clicável pela linha).
- 09/10: booleana 3D destrutiva na parede. O vão continua sendo registro lógico do hospedeiro.
- 11/10: título "Parametric Architecture" e botões de texto ("Simple wall", "Composite wall") no topo do formulário da parede.
- 09/10: autoatualização ou site que não existem. Nenhum recurso é anunciado antes de existir.
- 09/10: alterar `scene.saved_views` ou `scene.section_planes` sem passar pelo histórico (issue #310 do IngeTrazo).

## Adiado
- Portas e janelas com ferramenta própria, segundo clique para lado e giro, tamanhos editáveis na barra (ver `docs/NEXT.md`).
- Bloco visual da interface: tema, ícones legíveis, paleta que mostre tudo, abas no 0.5.8 (ver `docs/NEXT.md`).
- Barra personalizável pelo usuário (quais grupos e em que ordem).
- Vistas 3D, planta, corte e elevação com pavimento e escala (etapa 05). A escala 1:50 rege símbolos, hachuras e cotas e não trava o zoom; a altura de corte de 1,50 m é só proposta.
- Tramas vetoriais por material e escala (etapa 06).
- Compositor, consolidação do IFC e round-trip, com conferência em Archicad, FreeCAD e Bonsai (etapa 07).
- Ferragens e armaduras complexas como plugins; terreno avançado; botão de doação e manifesto resumido na paleta.

Ordem das etapas: 00 fundação, 01 aberturas, 02 portas e janelas, 03 paletas dessas ferramentas, 04 interface geral, 05 vistas, 06 representação 2D, 07 Compositor e IFC.
