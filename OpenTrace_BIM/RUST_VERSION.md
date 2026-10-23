# OpenTrace BIM 0.44.0 Rust

Esta versão instala o núcleo Rust ativo automaticamente: nenhum botão, variável,
configuração ou passo extra é necessário. Instale como plugin normal do IngeTrazo.
A DLL nativa Windows é empacotada junto do código, no local procurado pelo adaptador.
Se a DLL estiver faltando, as operações Rust informam erro; não há fallback silencioso.

Migração nesta versão:
- Alinhamento e distribuição dos objetos.
- Paredes curvas: amostragem geométrica da curva de referência.
- Aberturas poligonais: cálculo de área, colisões de segmentos e curvas das bordas.
- Lajes: amostragem de curvas, validação de cruzamentos, área e ponto-em-polígono.
- Vigas: curva horizontal compartilhada com paredes e perfil vertical circular Rust.
- Pilares curvos: curva de eixo compartilhada com o motor de paredes.
- Portas e esquadrias: cálculo nativo dos vértices de prismas e das ranhuras.
- Perfis complexos: área e classificação de ponto no contorno.

A interface, Qt/PySide6, gerenciamento de objetos e histórico, rotinas de mesh,
grande parte das ferramentas BIM, IFC e serialização continuam Python.
Isto não é uma reescrita integral do OpenTrace; inclui subrotinas nativas
em várias ferramentas. A migração integral não está concluída.

A cópia base foi verificada por SHA-256 contra o ZIP oficial 0.44.0:
b03455f4c24b95592e4ce671bdb85eb60e06bff02a617bcc497d8697fa40a937.

O workflow Windows compila cargo, executa testes e publica um artefato ZIP.
A validação real no IngeTrazo Windows ainda deve ser feita pelo usuário.

Não alterar main, publicar release ou atualizar catálogo.

Além dos testes Rust, o workflow compara milhares de casos diretamente com os
algoritmos Python do ZIP original, incluindo bordas curvas, interseções, perfis,
vigas e prismas.

## Ajustes de integração após teste no IngeTrazo (2026-10-23)

- Curvaturas de vigas e pilares editados não devem contaminar os valores da
  próxima criação. A memória de criação é separada da seleção/edição.
- Barra contextual tem página própria para Perfil Complexo, acesso à biblioteca,
  criação de novos perfis e menu de ações CAD 2D originais do IngeTrazo.
- A ação Opening, com uma laje selecionada, direciona para o editor de abertura
  poligonal já existente na laje. Aberturas em parede continuam inalteradas.
- Prévia de curvatura de aresta de abertura na laje limitada a 64 amostras para
  mitigar artefatos na viewport. Isto não modifica o renderizador e depende de
  confirmação no IngeTrazo Windows.

O CI valida sintaxe e compilação Rust, mas não substitui testes reais de Qt/GL.
