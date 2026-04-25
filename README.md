# Load Balancing Study

Projeto de benchmark para simular estratégias de load balancing e comparar o comportamento dos algoritmos sob diferentes padrões de tráfego, perfis de carga e limites de capacidade dos servidores.

## Visão Geral

O objetivo do projeto é permitir experimentos reproduzíveis com diferentes algoritmos de balanceamento de carga, variando:

- padrão temporal de chegada das requisições;
- capacidade dos servidores;
- tamanho das filas;
- custo de processamento das requisições;
- composição dos tipos de carga.

A simulação pode ser executada por interface gráfica em Streamlit.

## Algoritmos Disponíveis

Atualmente, o benchmark inclui os seguintes algoritmos:

- `round-robin`: distribui as requisições em ordem circular entre os servidores online.
- `random`: escolhe aleatoriamente um servidor online.
- `least-connections`: escolhe o servidor com menor carga atual, usando a ordem:
  - menos requisições ativas;
  - menos requisições na fila;
  - menor ID do servidor.
- `power of two choices`: escolhe aleatoriamente dois servidores online e seleciona o menos carregado entre eles, comparando:
  - requisições ativas;
  - tamanho da fila.

## Parâmetros Principais

Os principais parâmetros do benchmark são:

- `algorithm`: algoritmo ou conjunto de algoritmos a serem comparados.
- `duration`: duração total da simulação em segundos.
- `servers`: quantidade de servidores disponíveis.
- `max-concurrent`: número máximo de requisições atendidas simultaneamente por servidor.
- `queue-limit`: tamanho máximo da fila de cada servidor. Use `-1` para fila ilimitada.
- `seed`: semente opcional para tornar a geração de carga determinística.
- `total_requests`: total exato de requisições a gerar, quando desejado.
- `service-time`: tempo de serviço base das requisições, usado nos cenários que trabalham com tempo fixo de processamento.

## Parâmetros por Cenário

### Constant

- `rps`: taxa média de requisições por segundo.
- `service-time`: tempo base de serviço.

### Burst

- `base-rps`: taxa base de requisições por segundo.
- `burst-rps`: taxa durante a janela de pico.
- `burst-start`: instante em que o pico começa.
- `burst-end`: instante em que o pico termina.
- `service-time`: tempo base de serviço.
- `time-resolution`: resolução temporal usada para construir a janela de burst.

### Poisson

- `rps`: taxa média de requisições por segundo.
- `service-time`: tempo base de serviço.

### Pareto Long Tail

- `rps`: taxa média de requisições por segundo.
- `service-time-min`: tempo mínimo de serviço.
- `service-time-alpha`: parâmetro da distribuição de Pareto. Valores menores, acima de 1, produzem caudas mais pesadas.

## Cenários de Tráfego

Os cenários definem o padrão temporal de chegada das requisições:

- `constant`: mantém uma taxa média estável de requisições ao longo do tempo, com pequenas variações locais para evitar tráfego artificialmente rígido.
- `burst`: mantém uma taxa base e aumenta a intensidade durante uma janela específica de pico.
- `poisson`: gera chegadas estocásticas com taxa média controlada por `rps`, aproximando melhor tráfego real de produção.
- `pareto-long-tail`: mantém a taxa média de chegada, mas usa tempo de serviço com cauda longa, fazendo com que a maioria das requisições seja curta e algumas poucas sejam significativamente mais lentas.

## Perfis Gerais de Carga

Além do cenário temporal, cada requisição recebe um perfil geral de carga independente do cenário.

Tipos de carga atualmente usados:

- `read`: cerca de 70% a 73% das requisições.
- `write`: cerca de 18% das requisições.
- `report`: cerca de 4% das requisições.
- `auth`: cerca de 5% a 8% das requisições.

Cada tipo de carga também recebe um peso de intensidade:

- `below-expected`
- `expected`
- `above-expected`

O identificador final exibido nas métricas e na interface segue o formato:

- `read-below-expected`
- `write-expected`
- `report-above-expected`
- `auth-expected`

Os cenários não definem o tipo da carga. Eles definem apenas o padrão temporal de chegada e influenciam o peso atribuído a cada request. O tipo de carga é aplicado depois, como uma camada geral da simulação.

Na prática, isso permite representar:

- variação temporal de tráfego;
- mistura de tipos de operação;
- diferença de custo entre operações leves, médias e pesadas.

## Métricas Coletadas

O benchmark calcula as seguintes métricas:

- `total_requests`: total de requisições geradas.
- `served_requests`: total de requisições atendidas.
- `dropped_requests`: total de requisições descartadas.
- `drop_rate`: proporção de requisições descartadas sobre o total.
- `throughput_rps`: quantidade de requisições atendidas por segundo.
- `avg_latency_seconds`: latência média total, da chegada ao fim do atendimento.
- `p95_latency_seconds`: valor de latência que 95% das requisições não ultrapassam.
- `avg_wait_seconds`: tempo médio de espera antes do início do atendimento.
- `avg_service_seconds`: tempo médio efetivo de processamento.
- `server_distribution`: distribuição de requisições atendidas por servidor.
- `source_distribution`: distribuição por perfil final de carga, como `read-expected` ou `auth-above-expected`.

## Estrutura do Projeto

- `algorithms`: implementações dos algoritmos de balanceamento e contrato base.
- `cli`: leitura de parâmetros, montagem de workloads e execução da simulação via terminal.
- `scenarios`: definição dos padrões temporais de geração de requisições.
- `servers`: modelos de configuração e estado dos servidores.
- `load_profiles`: definição dos tipos de carga, pesos e multiplicadores de custo.
- `simulation`: núcleo da simulação, montagem das requisições, mistura de workloads e execução do balanceamento.
- `metrics`: cálculo e agregação das métricas após a simulação.
- `ui`: interface gráfica em Streamlit.
- `tests`: testes automatizados do projeto.

## Interface Gráfica

A interface gráfica foi construída com Streamlit e permite:

- selecionar algoritmos;
- ajustar os principais parâmetros da simulação;
- escolher o cenário;
- comparar métricas entre algoritmos;
- visualizar distribuição por servidor e por perfil de carga.

## Como Visualizar
https://loadbalancingstudy-vcvibkcxhzecvmh2eiv4pr.streamlit.app
