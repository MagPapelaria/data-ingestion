# Data Ingestion ETL

Este projeto implementa um pipeline de ETL (Extração, Transformação e Carregamento) para processar dados de pedidos obtidos por meio de uma API e armazená-los em um banco de dados PostgreSQL.

## Visão Geral do Sistema

O sistema é dividido em três módulos principais:

1. **Ingestão**  
   O módulo de ingestão realiza a comunicação com a API para obter os dados brutos. Ele utiliza a biblioteca `requests` para enviar requisições HTTP com cabeçalhos e parâmetros dinâmicos, configurados via variáveis de ambiente.

2. **Transformação**  
   Após a extração, os dados são processados e transformados para garantir a integridade e consistência. Isso inclui:
   - Conversão de datas para um formato padronizado.
   - Extração de nomes de franqueados e fornecedores.
   - Renomeação e estruturação de campos para um formato adequado ao banco de dados.

3. **Carregamento**  
   O módulo de carregamento é responsável por inserir os dados transformados no banco de dados PostgreSQL. Antes de realizar a inserção, o sistema verifica se o registro já existe, garantindo que apenas novos dados sejam adicionados.

---

## Funcionalidades

- **Conexão Segura com a API**  
  As informações de URL e chaves de autenticação são armazenadas em variáveis de ambiente para garantir segurança e flexibilidade.

- **Transformação Personalizada**  
  Os dados passam por um processo de limpeza que os prepara para serem armazenados no banco de forma consistente.

- **Controle de Duplicidade**  
  Antes de inserir um pedido no banco, o sistema verifica se ele já existe para evitar duplicações.

- **Modularidade**  
  O sistema foi projetado em módulos independentes (`ingest.py`, `transform.py`, `load.py`), o que facilita a manutenção e a escalabilidade.

---

## Tecnologias Utilizadas

- **Linguagem**: Python  
- **Bibliotecas**:
  - `requests` para comunicação com a API.
  - `psycopg2` para interação com o banco de dados PostgreSQL.
  - `python-dotenv` para gerenciar variáveis de ambiente.
- **Banco de Dados**: PostgreSQL
