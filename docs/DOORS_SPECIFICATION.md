# OpenTrace BIM — Especificação funcional da ferramenta Portas

**Versão da especificação:** 0.4 (decisões consolidadas das Rodadas 1–4)  
**Data da consolidação:** 13/10/2026  
**Status:** discussão de produto / especificação; **NÃO significa implementação, aprovação visual ou validação técnica**  
**Escopo da alteração no GitHub:** apenas este documento. Não alterar código, branch principal, release nem catálogo.  
**Rodada 5:** aberta, **sem respostas aprovadas** até esta revisão.

> **Como ler:** **DECIDIDO** = escolha explícita do mantenedor, incluindo correções posteriores. **DERIVADO** = consequência necessária ou interpretação de compatibilidade, sujeita a validação detalhada. **ABERTO** = questão ainda não decidida. **REFERÊNCIA EXISTENTE** = requisito anterior encontrado nos cadernos mestres ou código, sem constituir aprovação nova nesta discussão. As opções pré-selecionadas nas interfaces de perguntas NÃO contam como decisões enquanto não enviadas.

## 1. Objetivo e limites

Projetar uma ferramenta de portas paramétricas do OpenTrace BIM inspirada no fluxo arquitetônico de ferramentas como o Archicad, com inserção direta, representação 2D, geometria 3D, biblioteca de famílias, edição contextual e associação BIM. A discussão trata de **comportamentos e requisitos**; não autoriza publicação, instalação ou alteração do motor. Inspirar-se em padrões de UX não significa reutilizar código ou recursos proprietários.

O sistema distingue:

- **Porta hospedada:** ferramenta Porta tradicional; exige parede, associa objeto a um vão e acompanha o hospedeiro.
- **Porta solta:** modalidade escolhida **explicitamente** pelo usuário; objeto independente, sem parede e sem corte automático. Não é um fallback silencioso ao clicar fora da parede.

As duas modalidades podem compartilhar famílias e propriedades construtivas, mas a modalidade solta precisa suportar persistência sem IDs fictícios de parede/vão (**DERIVADO**).

## 2. Rodada 1 — Inserção, operações principais e representação

| ID | Tema | Decisão explícita | Observação |
|---|---|---|---|
| R1-01 | Inserção | **Dois cliques**: primeiro posição; segundo lado da dobradiça e sentido/giro da abertura | Para a porta convencional hospedada. |
| R1-02 | Face de referência | **Automática**, identificada a partir do cursor | Detalhes de alternância manual ainda podem ser especificados. |
| R1-03 | Âncora inicial | **Centro** | Âncoras esquerda/direita permanecem possibilidades do sistema existente. |
| R1-04 | Dimensões iniciais | **Repetir o último tamanho utilizado** | Não fixar 80×210 ou 90×210 como default universal. |
| R1-05 | Campo principal | Inicialmente **vão** como dimensão principal | **Complementado em R3-01 e R4-01:** oferecer escolha nominal/físico; nominal significa folha. |
| R1-06 | Biblioteca | Planejar todas as famílias, **implementar progressivamente** | R3 estabelece o subconjunto inicial obrigatório. |
| R1-07 | Excluir porta | **Excluir porta e respectivo vão juntos** | Uma operação reversível; não eliminar vãos de outros elementos. |
| R1-08 | Ângulos | **O mesmo ângulo para representação 2D e geometria 3D** | R2 fixa início em 90°. |
| R1-09 | Representação | **Configuração manual por objeto**, sem troca automática por escala | R4 complementa com parâmetros gráficos unificados. |
| R1-10 | Colisões | **Avisar**, permitir corrigir ou confirmar conscientemente | A integridade de malha deve continuar protegida. |
| R1-11 | Hospedagem | **Porta convencional precisa de parede** | Existe também a Porta solta, somente quando selecionada como objeto específico. |

**Comportamento de inserção (DECIDIDO):** porta hospedada exige host, primeiro clique fixa localização, segundo determina orientação. Posição de referência é automática pelo cursor e âncora inicial é central. Após cada inserção, os padrões do usuário podem ser repetidos, mas a política exata de continuidade da ferramenta não foi aprovada isoladamente.

**Consequência (DERIVADO):** alterar a orientação da folha não deve deslocar arbitrariamente o vão. Trocar o lado da dobradiça e inverter o sentido de abertura são operações distintas. A posição e o sentido devem ser apresentados claramente na prévia e na edição.

## 3. Rodada 2 — Construção, altura, detalhamento e materiais

| ID | Tema | Decisão consolidada | Nota de correção |
|---|---|---|---|
| R2-01 | Dimensão | Dimensões **nominais com folgas construtivas** adicionadas | Significado de nominal refinado: folha (R4-01). |
| R2-02 | Profundidade do batente | **Fixa, independente da espessura da parede** | Não autoesticar o batente ao engrossar a parede. |
| R2-03 | Plano do batente | **Deslocamento manual configurável** na espessura da parede | Qual referência acompanhar em futuras mudanças permanece aberto na R5. |
| R2-04 | Altura de referência | **Todas as três referências selecionáveis por porta:** base da parede, piso acabado ou nível do pavimento. **Default escolhido: nível do pavimento + deslocamento.** | **Correção posterior do mantenedor:** não restringir a apenas uma das três. |
| R2-05 | Detalhamento | **Três níveis selecionáveis quando implementados:** básico (folha + marco), arquitetônico (+ guarnições) e detalhado (+ ferragens modeladas). **Default: arquitetônico.** | **Correção posterior do mantenedor:** todos disponíveis, não um único nível rígido. |
| R2-06 | Guarnições | **Interna e externa independentes** | Parâmetros e acabamentos próprios. |
| R2-07 | Materiais | **Padrão: material da folha separado dos demais componentes**; opção de ativar materiais **diferentes para cada face da folha** | **Correção posterior explícita**; R3-10 limita a divisão por face à folha. |
| R2-08 | Ângulo inicial | **90°**, compartilhado por 2D e 3D | Sem separar ângulo gráfico e ângulo físico por padrão. |
| R2-09 | Porta solta | **Dois cliques**, posição e orientação | Ferramenta escolhida expressamente. |
| R2-10 | Porta sobre vão livre | **Oferecer adoção explícita** do vão existente; ele passa a pertencer à porta | Não tomar propriedade de forma silenciosa. |
| R2-11 | Troca de família | **Preservar dimensões, posição e parâmetros compatíveis** | Apenas parâmetros incompatíveis precisam ser reinterpretados. |

### Materiais — contrato de interface consolidado

- **Modo padrão:** materiais configurados por componente — folha, batente, guarnições e outros componentes pertinentes.
- **Opção ativável:** material **Face A** e **Face B da folha**, independentes. Quando desativada, ambas usam o material geral da folha.
- **Não estender automaticamente** a separação por face a todos os demais componentes: isso foi explicitamente rejeitado como padrão ampliado em R3-10.
- **DERIVADO:** desativar a diferenciação por face não deve destruir os valores personalizados que possam ser reativados depois.

### Altura e detalhamento — atenção às correções

As perguntas originais da R2 pediam uma escolha única. O mantenedor corrigiu esse formato: **as três referências de altura** e **os três níveis de detalhe** são recursos alternáveis **por porta**. As respostas originais indicam somente os **padrões iniciais**. Em nenhum momento a correção aprovou modo automático de LOD por escala.

## 4. Rodada 3 — Famílias, barra e biblioteca

| ID | Tema | Decisão explícita |
|---|---|---|
| R3-01 | Entrada dimensional | **Alternar entre modo nominal e modo físico** de dimensionamento; campos e medidas devem permanecer consistentes. |
| R3-02 | Folgas | **Padrão por família**, modificável na instância da porta. |
| R3-03 | Famílias da primeira etapa | **As quatro:** abrir simples, abrir dupla, correr e pivotante. |
| R3-04 | Inserção da correr | **Dois cliques**: posição e, depois, sentido/lado de deslizamento. |
| R3-05 | Correr embutida | **Representação simbólica inicialmente**, sem prometer cavidade real modelada. |
| R3-06 | Porta dupla | **Folhas independentes**, incluindo larguras, sentidos e ângulos individuais. |
| R3-07 | Pivotante | **Eixo com afastamento numérico livre**. |
| R3-08 | Barra contextual | **Grupo expansível com parâmetros específicos**, respeitando uma faixa contextual única. |
| R3-09 | Biblioteca | **Galeria visual** com miniaturas, categorias e favoritos. |
| R3-10 | Materiais por face | Configuração opcional **só para as faces da folha**; outros componentes têm materiais próprios. |

**Compatibilidade de interface (DERIVADO):** a expansão de parâmetros não pode virar um Ribbon permanente nem uma segunda toolbar fixa. A barra contextual continua sendo a única faixa sob o menu do IngeTrazo, com controles básicos comuns e grupos específicos sob demanda. O formato da expansão (popover, painel temporário, expansão na mesma faixa) **ainda está aberto na R5**.

**Escopo de famílias:** quatro grupos iniciais não significam todos os estilos existentes de portas logo na primeira entrega. A implementação geral da biblioteca continua progressiva (R1-06). R4 acrescenta variantes telescópicas à família correr já na primeira etapa.

## 5. Rodada 4 — Dimensões exatas, folhas, ferragens e representação

| ID | Tema | Decisão explícita |
|---|---|---|
| R4-01 | Significado da dimensão nominal | **Dimensão nominal da folha**, não do conjunto/recorte. |
| R4-02 | Folgas editáveis | **Esquerda, direita, superior e inferior independentes**. |
| R4-03 | Porta dupla redimensionada | **Redistribuir proporcionalmente** a largura entre as folhas. |
| R4-04 | Portas de correr | Primeira etapa **estendida**, incluindo modelos telescópicos; além das variantes sobreposta e embutida simbólica. |
| R4-05 | Trilho de correr | **Face da parede + afastamento numérico independente**. |
| R4-06 | Referência de pivô | Medir o afastamento do eixo **a partir da extremidade da folha**. |
| R4-07 | Segundo clique pivotante | Cursor define **lado do pivô e sentido**, afastamento permanece parâmetro numérico. |
| R4-08 | Biblioteca de folha | **Uma família com variantes** de desenho: lisa, almofadada, vidro, painéis, visor etc. |
| R4-09 | Ferragens segundo detalhe | **Básico:** sem ferragem 3D; **arquitetônico:** simplificadas; **detalhado:** completas. |
| R4-10 | Ferragens por face | **Mesmo conjunto por padrão, com separação opcional** para interna/externa. |
| R4-11 | Batentes e guarnições | **Biblioteca de perfis paramétricos**, editor de perfis livres poderá ser posterior. |
| R4-12 | Representação | **Configuração gráfica unificada por porta**, sem adaptação automática por escala. |
| R4-13 | Arco em planta | **Visível por padrão**, opção individual de ocultar. Ocultar o arco não muda o ângulo físico. |
| R4-14 | Marcação | **Código P01/P02… atribuído automaticamente**, marcador gráfico exibido por escolha. |
| R4-15 | Seleção | Clique seleciona **porta inteira**; contexto dá acesso aos componentes (folha, marco, ferragens). |

### Conciliação dimensional (DECIDIDO + DERIVADO)

- **DECIDIDO:** usuário pode alternar entre **modo nominal (medida da folha)** e **modo físico (medida do vão efetivamente cortado)**.
- **DECIDIDO:** há folgas por família, editáveis por instância e em quatro direções.
- **DERIVADO:** campos como largura da folha, largura externa do conjunto, abertura física e passagem livre precisam ser diferenciados.
- **DERIVADO:** apenas trocar o modo de leitura/entrada não deve alterar a geometria; uma edição de valor confirma o redimensionamento.
- **ABERTO:** regras e valores precisos para distinguir **folgas funcionais folha–batente** de **folgas de instalação batente–parede**. Não somar as mesmas folgas duas vezes.
- **ABERTO:** valores iniciais de folgas e limites geométricos por família, incluindo soleiras e batentes assimétricos.

### Conciliação da representação

- **DECIDIDO:** ângulo gráfico e ângulo da folha 3D são iguais; início em 90°, por folha quando houver duas.
- **DECIDIDO:** representação manual por objeto, com um **conjunto unificado de propriedades**; arco em planta visível por padrão, ocultável.
- **DERIVADO:** planta, corte e elevação têm geometrias gráficas diferentes, ainda que compartilhem a configuração do objeto.
- **NÃO DECIDIDO:** futuro override de representação por vista ou escala; não adicionar automaticamente nesta fase.

## 6. Inventário de parâmetros aprovado / necessário

### 6.1 Comuns a portas hospedadas

**Decididos:** família; modelo/variante; largura nominal da folha / modo dimensional físico; altura; quatro folgas ajustáveis; âncora central inicialmente; posição no hospedeiro; duas etapas de inserção; referência vertical selecionável; cota/deslocamento; plano e offset de batente; profundidade fixa; três níveis de detalhamento; materiais por componente; opcional face A/B da folha; guarnições interna/externa; representação manual; marcador; ID; configuração de ferragens.

**Derivados a calcular/expor:** largura/altura do recorte real; largura do conjunto; passagem livre; dimensões e tolerâncias vinculadas; ID estável da porta e do vão; geometria e propriedades compartilhadas entre barra e painel.

### 6.2 Abrir simples

**Decididos:** dobradiça/sentido escolhidos no segundo clique; ângulo 90° inicial comum a 2D/3D; arco em planta inicialmente visível; modelos de folha por variante; materiais e ferragens conforme seção geral.  
**Pendente:** comportamento definitivo dos controles de espelhamento/troca de dobradiça e seus atalhos.

### 6.3 Abrir dupla

**Decididos:** folhas A/B independentes (dimensões, sentido e ângulo), redimensionamento proporcional à razão atual das larguras, representação/ângulos próprios por folha.  
**Pendente:** folha ativa/passiva inicial, encontro entre folhas, ferrolhos, assimetria mínima, modo de inserção exato de conjunto com 2 cliques nos casos ambíguos.

### 6.4 Correr — sobreposta, embutida simbólica, telescópica

**Decididos:** inserção em dois cliques; segundo define direção/lado; trilho em face da parede com offset numérico; variantes sobreposta e embutida simbólica; telescópica no escopo inicial.  
**Pendente:** quantidade de folhas e trilhos, sobreposição, ordem de recolhimento, posição fechada/aberta, limites de passagem, representação 3D da embutida e eventual cavidade real futura. **Não declarar cavidade construída em paredes compostas enquanto houver somente símbolo.**

### 6.5 Pivotante

**Decididos:** posição do pivô como distância numérica da extremidade da folha; segundo clique escolhe lado e sentido; ângulo compartilhado entre 2D e 3D.  
**Pendente:** geometria de encontros e batente, folgas varridas pela rotação, conflitos com parede e posição do eixo na profundidade.

### 6.6 Porta solta

**Decididos:** ferramenta específica, duas etapas de inserção, sem necessidade de parede e sem abertura associada.  
**Pendente:** conversão explícita em porta hospedada, referência de elevação da porta solta e relação com vistas/IFC sem host.

## 7. Interface — distribuição e comportamento

**Barra contextual única (DECIDIDO anteriormente na interface geral e complementado nesta discussão):**
- A ferramenta Porta troca o conteúdo da faixa contextual sob os menus nativos.
- Mostrar família/modelo, dimensões principais, ancoragem e comandos de orientação relevantes.
- Permitir **expansão sob demanda** dos parâmetros específicos de abrir simples/dupla/correr/pivotante (R3-08), sem acrescentar Ribbon permanente.
- O tamanho da porta usado inicialmente repete o último tamanho (R1-04).
- **DERIVADO:** modo nominal/físico precisa estar identificável na interface para evitar erro de leitura.
- **REFERÊNCIA EXISTENTE:** barra e paleta compartilham a mesma fonte de dados, com sincronização bidirecional; detalhes de geometria por hotspots/radial permanecem na viewport/paleta.

**Paleta lateral:** galeria visual de famílias e variantes com miniaturas/favoritos, configuração completa de dimensão e folga, materiais, ferragens, perfis, representação, referência de cota, identificação BIM.

**Viewport:** prévia entre primeiro e segundo clique; seleção do conjunto; edição de componentes por comando contextual; alertas de colisão; edição gráfica conforme contrato preexistente da ferramenta de aberturas.

**REFERÊNCIA EXISTENTE do núcleo de portas:** três âncoras (esquerda, centro, direita); seis hotspots; superiores permitem largura/altura, inferiores largura/posição; inversão do giro. A decisão desta conversa estabelece o padrão central e a orientação em dois cliques, mas não ratifica individualmente cada atalho ou animação de widget.

## 8. Regras de dados, exclusão e integridade

1. **DECIDIDO:** Porta hospedada cria/possui vão em parede; porta solta não cria vão automaticamente.
2. **DECIDIDO:** adoção de abertura livre exige confirmação; uma vez adotada, o vão pertence à porta.
3. **DECIDIDO:** excluir a porta hospedada também exclui seu vão, inclusive quando adotado, e a porta solta remove somente seu objeto.
4. **DERIVADO:** exclusão, inclusão, adoção, troca e Undo/Redo devem ser operações coerentes, sem objetos órfãos ou supressão de vãos de terceiros.
5. **DECIDIDO:** substituição de família preserva dados compatíveis.
6. **DECIDIDO:** colisões geram aviso com possibilidade de correção ou confirmação, sem bloqueio indiscriminado.
7. **DERIVADO:** permitir confirmar uma colisão não autoriza salvar malha geometricamente inválida ou estado irrecuperável; esses casos exigem apresentação clara do impedimento técnico.
8. **REFERÊNCIA EXISTENTE:** parede é dona da geometria do recorte; porta é objeto separado vinculado por IDs de parede/abertura; manter GUIDs, persistência .igz, histórico e IFC (IfcDoor, IfcOpeningElement e relação de preenchimento) sem duplicidade.
9. **REFERÊNCIA EXISTENTE:** quando se recua a parede além de um vão, a lógica de abertura persistente não deve destruir seus IDs/valores; a extensão desse comportamento a todas as famílias ainda precisa de teste.

## 9. Decisões ainda abertas — NÃO aprovar por defaults da interface

### 9.1 Rodada 5 (formulário apresentado, mas sem respostas enviadas)

1. **Paredes curvas:** tangente local, corda ou escolha entre ambas.
2. **Paredes multicamadas:** recortar todas ou permitir seleção de camadas, com tratamentos de requadros.
3. **Parede muda espessura:** preservar offset do batente em relação à face, eixo ou posição absoluta; profundidade continua fixa.
4. **Porta parcialmente/totalmente fora da parede:** estado lógico/visual e política de edição.
5. **Folgas funcionais x folgas de instalação:** controles, associação às quatro direções e fórmulas.
6. **Adoção de vão pré-existente incompatível:** ajuste, substituição, confirmação e eventual recusa.
7. **Representação da porta embutida simbólica:** plano, 3D, avisos e nomenclatura.
8. **Conjuntos com bandeiras e laterais:** composição e identificação.
9. **Telescópicas:** arranjo de folhas/trilhos/limites, parametrização.
10. **Converter porta solta em hospedada:** quando, como e com qual intervenção geométrica.
11. **Tipos x instâncias:** herança, alterações em lote, desvinculação de valores.
12. **Identificação:** convenção de códigos por tipo ou instância, renumeração.
13. **Expansão da faixa contextual:** localização exata e como recolher sem perder viewport.
14. **Espelhamento/duplicação:** regras para preservar âncora, orientação, parâmetros e hospedagem.

### 9.2 Questões transversais adicionais

- Definir os números reais de folgas por família, a cadeia de dimensões, espessuras e passagem livre; não inventar normas.
- Verificar como a folha de 90° se comporta em perspectiva quando se deseja visualização 3D fechada: a sincronização 2D/3D foi escolhida expressamente e não pode ser alterada silenciosamente.
- Qual modo dimensional aparece primeiro por default quando existe a alternância nominal/físico.
- Dimensões iniciais de ferragens, perfis, guarnições, folhas duplas e padrões de materiais.
- Critérios precisos para tratamento de piso acabado e mudança de referência vertical sem mover inesperadamente a porta.
- Comportamento do segundo clique em modelos de várias folhas, funções específicas dos hotspots e acessibilidade de atalhos.
- Formato do código automático, sua persistência e conflitos de numeração.
- Política de salvar favoritos/presets e atualização dos tipos já instanciados.

## 10. Estado de implementação — não confundir especificação com entrega

O código e os cadernos anteriores registram **base experimental** para porta de abrir, janela, vínculo com aberturas, âncoras e alguns controles. Essa base **não comprova** a existência das quatro famílias completas, telescópicas, editor de perfis, ferragens detalhadas, porta solta, materiais por face ou barra definitiva. A interface geral teve reprovação visual documentada e ainda depende de validação em Windows.

**Nenhuma implementação, teste, release ou aprovação visual é reivindicada por este documento.** É exclusivamente um registro das decisões e das pendências desta conversa.

### Referências internas

- [Caderno mestre do desenvolvimento](DEVELOPMENT_MASTER.md)
- [Caderno mestre de interface](INTERFACE_MASTER.md)
- [Núcleo experimental de contratos de portas e janelas](../OpenTrace_BIM/door_window_core.py)
- [Geometria experimental de portas e janelas](../OpenTrace_BIM/door_window_geometry.py)

## 11. Critérios para futuras atualizações deste documento

1. Anotar nova decisão com ID, data, rodada e autor da aprovação; preservar o histórico quando uma decisão substituir outra.
2. Separar explicitamente **aprovado**, **sugerido**, **consequência derivada**, **pendente** e **implementado/testado**.
3. Não transformar alternativas selecionadas por padrão em formulários em decisões se o usuário não enviou as respostas.
4. Não alegar paridade com Archicad nem aprovar UX sem validação real.
5. Não alterar código, caderno mestre, versão pública ou branch principal apenas porque esta especificação foi aprovada para registro.

---

**Resumo:** Rodadas **1–4 consolidadas**, correções posteriores de **R2-04, R2-05 e R2-07** incorporadas, **Rodada 5 ainda aberta**, implementação **não autorizada**.
