# OpenTrace BIM — Caderno mestre EXCLUSIVO da interface

**Registro:** 11/10/2026 · **Origem principal:** conversa **“Melhorias De Interface”** (09/10/2026), complementada pelas quatro capturas da conversa trazidas novamente em 11/10/2026 e pelo [caderno geral](DEVELOPMENT_MASTER.md).  
**Repositório:** [lelopes05/opentrace-bim](https://github.com/lelopes05/opentrace-bim) · **Branch de trabalho:** dev/opening-controller-integration-2026-10-10 · **PR:** [#8, experimental](https://github.com/lelopes05/opentrace-bim/pull/8).  
**Caráter deste documento:** especificação de **experiência e interface**, separada de geometria e motores BIM. É fonte de consulta obrigatória para qualquer alteração visual.

> **Limite documental importante:** o histórico recuperável da conversa original inclui decisões, trechos resumidos e mensagens datadas, **não uma transcrição integral verificável**. As quatro capturas fornecidas pelo mantenedor foram usadas para reconstruir diagramas e pormenores visíveis. Itens não comprovadamente aprovados aparecem como **proposta/pendente**, nunca como decisão ratificada. Esta versão não declara implementadas telas que só foram desenhadas.

## 1. Decisão central — uma barra CONTEXTUAL, não um Ribbon fixo

**APROVADO (09/10):** uma **faixa contextual dinâmica, imediatamente sob os menus nativos do IngeTrazo**, próxima ao menu Arquivo. Ela muda **conforme a ferramenta ativada OU o objeto selecionado**, exibindo em primeiro plano:

1. **Métodos de construção** e pontos/posições de inserção da ferramenta ativa.
2. **Parâmetros mais utilizados** para a criação ou operação corrente (dimensões, cotas, níveis, alinhamento, estrutura).
3. Acesso imediato sem obrigar a abrir paletas complexas.

**O que NÃO foi aprovado:** reproduzir um Ribbon tradicional com famílias inteiras de ícones sempre expostas, acrescentar uma segunda ou terceira barra permanentemente carregada, ou ocupar mais viewport com barras duplicadas. A imagem de uma barra **fixa** com blocos “Principal / Elementos BIM / Aberturas / Modificação / Utilitários” é **apenas uma interpretação ilustrativa posterior**, **não** substitui esta decisão. A barra contextual precisa ser **opcional, recolhível e econômica em altura**. O menu original do IngeTrazo permanece.

**Diagrama vetorial reconstruído a partir das decisões e exemplos:**  
![Esquema da barra contextual e paleta lateral](assets/interface/contextual-toolbar.svg)

Esse SVG é um **diagrama de requisitos** (não screenshot ou implementação), contendo modos Parede/Porta e a separação viewport/paleta. Não se deve usá-lo como comprovação de código.

### Regra de contexto

| Estado | Conteúdo esperado na faixa | Ação |
|---|---|---|
| Sem ferramenta BIM ou seleção | Estado compacto, indicação da ferramenta corrente quando aplicável | Não expandir famílias desnecessárias |
| Ferramenta **Parede** ativa | Métodos construtivos, geometria reta/curva, referência/alinhamento, simples/composta, espessura, altura, níveis | Parâmetros de **criação** da próxima parede |
| Ferramenta **Laje/Pilar/Viga/Abertura** ativa | Métodos próprios da ferramenta, inserção e atributos fundamentais | Parâmetros de **criação** do próximo elemento |
| **Parede** selecionada | Atributos básicos e contexto da parede existente | Seleção **não** deve iniciar automaticamente nova parede |
| **Porta/Janela** selecionada | Largura, altura, ancoragem, giro/orientação quando aplicável | Atalhos rápidos; edição especializada segue na paleta |
| Editando vértice/aresta/hotspot | Nenhum editor geométrico complexo novo na barra | Paleta lateral + radial/hotspots coordenam a edição |
| Barra recolhida | Ocupa o mínimo possível; comando de reabrir | Não destruir nem alterar a ferramenta ativa |

**Sincronização bidirecional aprovada:** alterar, por exemplo, a espessura na faixa superior atualiza a mesma propriedade na paleta lateral; ajustar o valor lateral atualiza a faixa. **Uma única fonte de verdade** por propriedade, sem cadastros paralelos. Edição rápida de dimensões simples é admissível na faixa; **subpaletas, edição de vértices/arestas e propriedades avançadas NÃO vão para a barra**.

### Representação compacta do comportamento discutido

~~~text
Menus nativos: Arquivo  Editar  Câmera  Desenhar  Ferramentas  Janela  Ajuda
────────────────────────────────────────────────────────────────────────
OpenTrace BIM — PAREDE   [métodos: reta / retângulos / arcos ...]
                        [alinhamento] [simples/composta] [0,15 m] [3,00 m] [níveis]

   Trocar ferramenta OU selecionar outro elemento → MESMO espaço, outro conteúdo

OpenTrace BIM — PORTA    [0,90 m] [2,10 m] [Inverter giro] [Ancoragem ▾]

   Recolher ⇧ → barra minimizada; viewport recupera espaço
~~~

**Importante:** o exemplo numérico 0,15 m / 3,00 m / 0,90 m / 2,10 m representa o **estado ilustrativo mostrado na conversa**, não valores padronizados para todos os projetos.

## 2. Organização visual e iconografia

**APROVADO:**

- **Modos construtivos apresentados por ícones**, acompanhados de **mouse-over/tooltips**; o conjunto recebe **título pequeno** (“Mét. construtivos”, “Alinhamento” etc.). Evitar etiquetas de texto longas em cada opção.
- **Redundância funcional aceita**: pode haver um método na barra, na paleta e/ou em menu; não significa criar motores geométricos independentes.
- Agrupamento por **tarefa/contexto**, com bom espaçamento e hierarquia; preservar viewport.
- Preservar a **paleta lateral com cabeçalho horizontal**, conteúdo recolhível, seções e possibilidade de retração/ancoragem.
- A barra precisa coexistir com os recursos nativos do IngeTrazo, sem assumir controle sobre atalhos, seleção ou viewport.

**ADIADO:** permitir que cada usuário escolha quais grupos aparecem na barra e em qual ordem (referência ao Archicad). Primeiro consolidar um arranjo previsível e funcional. **Não inventar ícones genéricos iguais para ferramentas diferentes**: cada modo precisará de um símbolo claro, com dica de uso.

**CRITÉRIO NEGATIVO DE ACEITAÇÃO:** se uma versão acrescentar apenas texto pequeno “Abertura / Porta / Janela” no topo, mantendo o amontoado original de ferramentas, **ela NÃO cumpriu esta etapa de interface**.

## 3. Inventário dos métodos construtivos e parâmetros

Reconstituição da tabela discutida na conversa. O inventário representa **contrato de UX e funcionalidades a conferir**, não garantia de que todos os motores estejam disponíveis.

| Ferramenta | Métodos/controles rápidos discutidos | Parâmetros principais |
|---|---|---|
| **Paredes** | Reta; retângulo por diagonal; retângulo por base; arco normal; arco por centro; arco por três pontos; parede simples/composta; alinhamento | Espessura, altura, nível de base e topo |
| **Lajes** | Retângulo por diagonal; base + largura; polígono; simples/composta | Espessura, nível e cota |
| **Pilares** | Seção retangular, circular ou perfil complexo; ponto de inserção | Seção, altura, níveis base e topo |
| **Vigas** | Seção retangular, circular ou perfil complexo | Largura, altura, nível e cota |
| **Aberturas livres** | Tipo de vão (retangular/poligonal, conforme motor validado); método de inserção/ancoragem | Largura, altura, peitoril/cota, posição |
| **Portas** | Ferramenta dedicada; ponto de ancoragem à esquerda/centro/direita; sentido do giro | Largura, altura, giro, ancoragem |
| **Janelas** | Ferramenta dedicada; ancoragem e parâmetros coerentes com o vão hospedado | Largura, altura, peitoril/cota |

**Regra de prioridade herdada da conversa:** primeiro **como construir**, depois as dimensões e atributos essenciais. Ferramentas com modos ainda não implementados devem aparecer indisponíveis/identificados como futuros ou permanecer ocultas; **não oferecer controles que não funcionam**.

**Detalhe das portas já decidido no projeto:** um único comando de inverter giro; hotspot superior para altura; inferiores para posição; largura pelos hotspots adequados; edição via paleta radial/hotspots e paleta lateral. Não transformar isso em sequência de botões permanentes na faixa contextual.

## 4. Divisão obrigatória de responsabilidades

| Superfície | Responsabilidade | Não deve fazer |
|---|---|---|
| **Faixa superior dinâmica** | Modos de construção e atributos básicos/rápidos associados à ferramenta/seleção | Edits especializados, listas profundas de configurações, centenas de botões |
| **Paleta lateral ancorável** | Biblioteca de tipos, propriedades BIM, configurações completas, materiais/camadas, perfis, inclinações, edição detalhada | Repetir de forma desordenada dados já editáveis na faixa |
| **Radial/hotspots na viewport** | Escolha contextual sobre elemento selecionado (vértice/aresta/eixo), gestos geométricos, confirmação/cancelamento | Virar uma nova barra global; corromper seleção ou história |
| **Menus nativos/menus de acesso** | Encontrar comandos, incluindo redundância permitida, e acionar o mesmo mecanismo da barra | Registrar ferramentas concorrentes ou duplicar comandos de modelagem |

### Regras de seleção/edição da paleta radial

- Selecionar objeto existente implica **contexto de edição**, não início de nova criação.
- Clicar vértice, aresta ou hotspot define **o elemento lógico exato**; as opções mudam com o contexto.
- Novo clique substitui ou fecha o contexto anterior; clique no vazio pode retornar à ferramenta Selecionar, conforme a lógica já adotada para as paletas.
- Comandos de geometria precisam funcionar **repetidamente**, incluindo mais de uma edição da mesma abertura/aresta, com Undo/Redo sem perder ID do objeto nem seleção.
- Para as aberturas, referência de UX é o **editor de lajes**, mas o editor de paredes não deve prometer curvas/chanfros/arredondamentos ainda não implementados.

## 5. BIM e Informações do Projeto — separar responsabilidades

**APROVADO:** a aba/paleta BIM antiga mistura registro do empreendimento, IFC, atributos e configurações avançadas, tornando a interface pesada. Separar um acesso específico **ⓘ Informações do Projeto**, no **cabeçalho horizontal da paleta lateral**, abrindo a página correspondente **na própria paleta**, sem abrir janela desnecessária.

**Esquema conceitual reconstruído da captura:**

~~~text
[Paleta lateral OpenTrace BIM]
[Elementos] [Propriedades] [BIM] [ⓘ Informações do Projeto] [?]

┌─ ⓘ Informações do Projeto ─────────────────────────────────┐
│ IDENTIFICAÇÃO                                             │
│ Nome do projeto · Cliente · Localização · Descrição       │
├───────────────────────────────────────────────────────────┤
│ RESPONSÁVEIS                                              │
│ Autor · Escritório / Organização                          │
├───────────────────────────────────────────────────────────┤
│ ESTRUTURA DO PROJETO                                      │
│ Terreno · Edifício · Pavimentos / níveis existentes        │
└───────────────────────────────────────────────────────────┘
~~~

- **Manter o cadastro BIM já existente**, ampliando-o com Cliente/Localização e sem duplicar project metadata.
- **Reutilizar dados existentes dos níveis/pavimentos do IngeTrazo**; não criar outro gerenciador de níveis com informações concorrentes.
- **Separar** identificação do projeto de importar/exportar IFC e propriedades especializadas.
- A conversa mostrou a intenção de **três grupos recolhíveis** na aba BIM, porém os respectivos nomes/ordem não estão recuperáveis com segurança. **PENDENTE DE CONFIRMAÇÃO**; não inventar estrutura como decisão aprovada.
- Símbolo **ⓘ** tem uma função definida: cadastro do empreendimento, não ajuda genérica nem comando IFC.

## 6. Alinhar e distribuir em X / Y / Z

A funcionalidade de interface foi discutida para uma paleta ancorável, com botão próprio **↔**, não como modo construtivo de parede.

**Contrato funcional:** alinhar por **início / centro / fim** conforme os limites dos elementos, nos **eixos globais X, Y ou Z**; distribuir **espaço livre igual** entre ao menos **três** objetos, preservando os extremos; seleção com ao menos **dois** objetos para alinhamento. Aplicar como ação atômica undoável. A primeira versão aceita apenas **grupos/componentes completos** da cena principal, não faces/arestas soltas nem edição interna de grupo. Deixar esse limite claro ao usuário.

A barra dinâmica pode oferecer **atalho para abrir o painel**, sem colocar todos os ajustes da ferramenta de alinhamento permanentemente no topo.

## 7. Manual, ajuda contextual, Sobre e “O que há de novo”

**APROVADO na conversa:**

- Botão **?** e ajuda por ferramenta, com linguagem clara e **janela organizada por capítulos**.
- Priorizar **texto e desenhos/símbolos explicativos**; não construir manual com mockups de capturas de tela que envelhecem a cada atualização.
- A primeira página do manual de **cada nova versão** é **“O que há de novo”**.
- Janela **Sobre** com informações reais de projeto, licença, GitHub, discussão do IngeTrazo e mecanismo oficial de atualização (quando disponível e verificado). **Não inventar website nem anunciar autoatualização inexistente.**
- Manifesto institucional “OpenTrace BIM — Livre, gratuito e para todos!” já aprovado em outro registro: manter a íntegra oficial sem reescrever seu teor; versão resumida prevista para espaço institucional da paleta e manual. Botão de doação ficou **para depois** das melhorias da interface.

**Detalhe de disponibilidade:** a existência de uma proposta de “atualizador” na ajuda/Sobre **não prova** que verificação automática, download ou instalação automática estejam implementados.

## 8. Vistas arquitetônicas, cortes e escala de representação

Parte da conversa tratou do futuro ambiente de documentação arquitetônica. Este capítulo é **requisito de interface para fases posteriores**, não declaração de entrega atual.

**Modelo de interação proposto:** alternar **3D / Planta / Corte / Elevação**; quando pertinente, selecionar **pavimento** e **escala de representação** (ex.: **1:50**). O 3D permanece livre; a planta é gerada por **corte horizontal real** do mesmo modelo. Cenas devem registrar câmera, tipo de vista, corte, nível e escala, sem clonar a geometria.

**Diagrama da proposta trazida na captura:**

~~~text
Vista arquitetônica                                    [Proposta]
Vista:       (3D)   (Planta)   (Corte)   (Elevação)
Escala:      [1:50                       ▾]
Pavimento:   [Pavimento 0                ▾]
~~~

- A escala controla **símbolos, hachuras, espessura gráfica e cotas** da documentação, **não congela o zoom**.
- Aproximar/afastar a câmera não deve alterar o nível de detalhamento arquitetônico definido para a vista.
- A escala **física da imagem no monitor** é tema distinto, dependente de tamanho/calibração do dispositivo: **não prometer** sem suporte real.
- Reutilizar **cenas, seções, câmera, níveis e Compositor do IngeTrazo**; não criar um segundo motor de renderização/geométrico.
- Na vista 3D livre, optar por representação simples; nas vistas arquitetônicas, representação técnica. **Tramas vetoriais paramétricas** dependem do material/corte/escala e pertencem a uma etapa posterior.
- **Altura de corte da planta em 1,50 m** apareceu como **proposta ilustrativa** da conversa, **não como constante universal aprovada**. Torná-la parâmetro de vista quando implementado.

## 9. Referências de design e limites de reaproveitamento

**Archicad:** referência para **Info Box** compacto: métodos de construção, alinhamento, estrutura e dimensões à frente; configuração extensa no painel e agrupamentos personalizáveis numa fase seguinte. Não copiar indiscriminadamente a interface.

**ArchXQ para IngeTrazo:** referência observada para **biblioteca/contexto por seleção** (famílias, miniaturas, dimensões e troca de tipo em tempo real). Foi **referência para estudar**, não exigência de reproduzir seus componentes ou prova de suporte no OpenTrace.

**IngeTrazo:** é o host, e seus mecanismos de viewport, grupos, seleção, cenas, materiais, atalhos e história devem ser reutilizados. O OpenTrace acrescenta organização BIM/arquitetônica e comandos especializados, não duplica tudo.

## 10. Mapas de estados para implementação

~~~mermaid
flowchart TD
    A[Evento no host] --> B{Ferramenta ativa ou elemento selecionado?}
    B -->|Nenhum contexto BIM| C[Faixa recolhida ou minima]
    B -->|Ferramenta de criacao| D[Metodos construtivos + parametros iniciais]
    B -->|Objeto selecionado| E[Controles rapidos daquele tipo]
    E --> F[Paleta lateral para edicao detalhada]
    D --> G[Aplicar mesmo motor nativo de criacao]
    F --> H[Radial e hotspots para geometria]
    G --> I[Undo/Redo e modelo unico]
    H --> I
~~~

~~~text
┌──────────────────── IngeTrazo ─────────────────────────────────┐
│ MENU NATIVO — não substituído                                 │
├───────────────────────────────────────────────────────────────┤
│ OPENTRACE — UMA FAIXA CONTEXTUAL RECOLHÍVEL                    │
├──────────────────────────────────────┬────────────────────────┤
│ VIEWPORT NATIVA                      │ PALETA LATERAL          │
│ 3D / seleção / hotspots / radial     │ cabeçalho horizontal    │
│                                      │ grupos recolhíveis      │
│                                      │ edição e BIM avançado   │
└──────────────────────────────────────┴────────────────────────┘
~~~

A primeira imagem SVG e estes esquemas **reproduzem as ideias apresentadas nas capturas**, não fornecem evidência de entrega. Nenhum desenho deve induzir criação de controles inoperantes.

## 11. Estado REAL do repositório e diferenças entre “código” e “interface entregue”

**Base histórica confirmada no caderno geral até 10/10/2026:**

| Bloco | Estado registrado | Evidência / ressalva |
|---|---|---|
| **B1 — Informações do Projeto** | Integrado experimentalmente ao PR #8 | Não equivale a redesenho de toda a interface |
| **B2 — Alinhar/distribuir X/Y/Z** | Integrado experimentalmente ao PR #8 | Mesma ressalva |
| **B1+B2 — CI** | 58 testes puros + 60 testes host/PySide6 offscreen; ZIP experimental confirmado | [Run 38063649346](https://github.com/lelopes05/opentrace-bim/actions/runs/38063649346), SHA fb4c8a1f; **118 testes não são validação visual no Windows** |
| **B3a — Menus** | Código de organização arquitetônica registrado posteriormente em workspace_menu.py | Caderno anterior explicitamente exige gate próprio; **não presumir** que integra o ZIP 38063649346 |
| **B3b — Barra contextual DINÂMICA** | **Pendente** | O objetivo fundamental da conversa de interface ainda não está entregue |
| **B4 — Manual / Sobre** | Pendente de implementação/validação conjunta | Não anunciar autoatualização antes de confirmar |
| **B5 — Aceitação visual** | **Pendente** | Precisa de teste real no Windows/IngeTrazo |
| **Etapa 05 — Vistas** | Planejamento / capacidades anteriores dispersas; integração arquitetônica pendente | Não vender o controle 1:50/pavimentos como operacional |
| **Etapa 06 — Representação 2D/tramas** | Posterior | Sem claim de conclusão |

O mantenedor testou uma versão dita “interface atualizada” e relatou, em **11/10/2026**, a **mesma barra superior congestionada, ferramental OpenTrace misturado ao IngeTrazo, botões Abertura/Porta/Janela mal organizados e paleta lateral visualmente inalterada**. **Registrar como falha de aceitação do redesign**, independentemente da passagem em CI de B1/B2.

**REGRA INEGOCIÁVEL:** não rotular B1/B2 como **“reformulação da interface concluída”**. O objetivo-chave **é B3b**, seguido da aprovação visual B5. Preservar a release pública 0.12.9 e não mesclar na main ou publicar release/catálogo sem autorização.

## 12. Plano operacional — blocos grandes e frentes paralelas

Acordo de execução: trabalhar em **blocos substantivos**; o mantenedor valida a aparência/usabilidade e o assistente assume auditoria de arquitetura/código; manter frentes A (aberturas) e B (interface) paralelas quando não conflitam.

**Bloco UI-1 — Fundação e integração (B1/B2):** checar que Informações do Projeto e Alinhar/Distribuir coexistem sem duplicação, com estado/Undo e labels corretos. Já há código e gate registrados; evitar refazer.

**Bloco UI-2 — Barra dinâmica de verdade (B3b, PRIORIDADE VISUAL):** ocupar um único espaço próximo ao menu; conectar ao estado real de ferramenta/seleção; mapear métodos por ícones e títulos pequenos; parâmetros com sincronização; recolher; **preservar** atalhos/toolbar do host, sem duplicação. Teste com Parede → Porta → Laje → objeto selecionado → Selecionar.

**Bloco UI-3 — Hierarquia e menus (B3a + paleta):** organização coerente entre menus/paleta/barra; cabeçalho horizontal; grupos recolhíveis; ferramenta dedicada de abertura onde já suportada; acessibilidade dos métodos; nenhuma ação duplicada.

**Bloco UI-4 — Ajuda/Sobre (B4):** manual contextual, “O que há de novo”, links verdadeiros e documento institucional aprovado sem adulteração.

**Bloco UI-5 — Aceitação Windows (B5):** iniciar IngeTrazo real; testar aparência em viewport vazia e com paredes/lajes/vigas/pilares/portas/aberturas, foco/seleção, redimensionamento, barra recolhida, atalhos, persistência, mouse-over, Undo/Redo. Confirmar que B3b realmente muda a tela. **Só então** marcar redesign aceito.

**Bloco UI-6 — Vistas e representação (Etapas 05/06):** habilitar modo arquitetônico, pavimentos/corte/escala, depois cotas/símbolos/tramas; testar IFC/Compositor em etapa transversal, sem antecipar interface fictícia.

### Checklist mínimo de aceitação da barra

- [ ] Uma **única faixa contextual** logo abaixo da região de menus do IngeTrazo.
- [ ] Ao selecionar a ferramenta Parede, surgem seus métodos **em ícones + tooltip**, espessura, altura e referências coerentes.
- [ ] Ao mudar para Laje, somem os controles exclusivos da Parede, e os de Laje surgem **no mesmo lugar**.
- [ ] Ao selecionar uma Porta, surgem largura/altura/giro/ancoragem sem iniciar criação involuntária.
- [ ] Valores básicos mantêm **sincronia de ida e volta** com a paleta lateral.
- [ ] Edição geométrica avançada fica na paleta/radial, nunca numa faixa de dezenas de controles.
- [ ] Barra pode ser recolhida e restaurada sem perder ferramenta ou seleção.
- [ ] Não há botões inertes, toolbar OpenTrace duplicada, campos desatualizados ou degradação dos comandos nativos.
- [ ] Cabeçalho lateral é horizontal, propriedades avançadas recolhíveis, ⓘ mostra Projeto na mesma paleta.
- [ ] Screenshot e teste manual do **IngeTrazo no Windows** demonstram a mudança, além dos testes headless.
- [ ] Nenhuma publicação de release/main/catálogo ocorre sem autorização.

## 13. Dúvidas e propostas ABERTAS — não inventar aprovação

1. Quais serão os **três grupos e nomes definitivos** de subdivisão BIM mencionados no fim da captura?
2. Conjunto final, ordem e desenho de **todos** os ícones construtivos (necessita inventário por ferramenta e validação visual).
3. Implementação exata de ocultar/recolher a faixa: altura, persistência e opção em menu, sem disputar com toolbars do host.
4. Configuração individual de grupos/ordem da barra: **adiada**.
5. Altura-padrão do corte e detalhes das representações por escala: **propostos**, a validar tecnicamente.
6. Motor de atualização: apenas **previsto/referenciado**, comportamento real exige auditoria própria.
7. Extensões futuras (escadas, terreno avançado, esquadrias completas, símbolos, hachuras sofisticadas): **não confundir com UI já entregue**.

## 14. Como manter este caderno

Em toda alteração de interface, registrar **data / branch / commit / áreas visivelmente modificadas / resultado real em Windows / teste automatizado e número / pendências / imagem ou esquema atualizado**. Atualizar este documento **antes** de afirmar que uma interface foi entregue. O [caderno geral](DEVELOPMENT_MASTER.md) passa a apontar aqui e conserva a **ordem oficial 00–07**, sem duplicar estas decisões. Código experimental permanece no [PR #8](https://github.com/lelopes05/opentrace-bim/pull/8).

**Ordem oficial mantida:** 00 fundação; 01 aberturas; 02 portas/janelas; 03 paletas dessas ferramentas; 04 interface geral (**este caderno**); 05 vistas; 06 representação 2D/tramas; 07 Compositor, IFC e consolidação. A **frente B de interface roda em paralelo à frente A de aberturas**.

**Fontes e rastreabilidade:** “Melhorias De Interface”, 09/10/2026 (registro recuperado parcialmente); quatro capturas republicadas pelo mantenedor em 11/10/2026 (barra e fluxos de projeto/vista); DEVELOPMENT_MASTER.md na branch acima, especialmente “Decisão vigente — grandes blocos paralelos” e “Continuação do bloco B3”. Diagramas reproduzidos como SVG e esquemas neste arquivo; **não dependem de URLs temporárias da conversa**.
