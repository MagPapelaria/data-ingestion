# Data Ingestion ETL

Este projeto implementa um pipeline de ETL (Extração, Transformação e Carregamento) para processar dados de pedidos obtidos por meio de uma API e armazená-los em um banco de dados PostgreSQL.
 
## Visão Geral do Sistema

O sistema é dividido em três módulos principais:

*Ingestão*
O módulo de ingestão realiza a comunicação com a API para obter os dados brutos. Ele utiliza a biblioteca requests para enviar requisições HTTP com cabeçalhos e parâmetros dinâmicos, configurados via variáveis de ambiente.

 *Transformação*
Após a extração, os dados são processados e transformados para garantir a integridade e consistência. Isso inclui:

> -Conversão de datas para um formato padronizado.
> -Extração de nomes de franqueados e fornecedores.
> -Renomeação e estruturação de campos para um formato adequado ao banco de dados.

*Carregamento*
O módulo de carregamento é responsável por inserir os dados transformados no banco de dados PostgreSQL. Antes de realizar a inserção, o sistema verifica se o registro já existe, garantindo que apenas novos dados sejam adicionados.

