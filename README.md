# 📦 Central de Pedidos - Coleta e Atualização Automatizada

Este projeto tem como objetivo centralizar e automatizar a coleta de dados de pedidos feitos pelos franqueados através da API da Central do Franqueado. Ele é responsável por extrair as informações essenciais dos pedidos, armazená-las de forma estruturada no banco de dados da empresa e manter os dados atualizados com base em novos status fornecidos pela API.

---

## 🧠 Objetivo do Projeto

- Reduzir o trabalho manual de coleta e digitação de dados de pedidos.
- Padronizar e garantir a qualidade dos dados que entram no banco.
- Possibilitar análises mais confiáveis e rápidas sobre o volume, origem e status dos pedidos feitos.
- Atualizar automaticamente os status de pedidos previamente cadastrados, evitando retrabalho e inconsistências.

---

## 🏗️ Visão Técnica

### Módulos principais:

- **`main.py`**  
  Ponto de entrada da aplicação. É responsável por iniciar o processo de coleta e atualização.

- **`api.py`**  
  Faz a requisição à API de pedidos, com estratégia de retry configurada para garantir robustez na comunicação.

- **`processador.py`**  
  Contém a lógica de extração e transformação dos dados dos pedidos, e orquestra o envio ao banco de dados.

- **`db.py`**  
  Gerencia a conexão com o banco PostgreSQL via pool de conexões e executa os comandos de inserção e atualização.

- **`utils.py`**  
  Funções auxiliares, como tratamento de strings, normalização e dicionários fixos (ex.: nomes dos meses).

---

## 🧩 Principais Funcionalidades

- **Coleta diária de pedidos** com base na data definida no código (`params` da API).
- **Extração de dados brutos** como: número do pedido, status, fornecedor, franqueado, valor total e data.
- **Transformação padronizada** dos dados: normalização de nomes, remoção de acentos e capitalização.
- **Inserção em lote (batch)** de novos pedidos com tratamento de conflitos (ignora duplicados).
- **Atualização de status** de pedidos já existentes.
- **Log detalhado** das execuções para rastreabilidade e auditoria.

---

## 🧪 Tecnologias Utilizadas

- **Python 3.10+**
- **PostgreSQL**
- **Requests** (requisições HTTP)
- **psycopg2** (conexão com banco)
- **dotenv** (gerenciamento de variáveis de ambiente)
- **logging** (registro estruturado de execução)

---

## 🔐 Segurança e Controle

- As credenciais de banco de dados e da API são carregadas através de variáveis de ambiente (.env), garantindo segurança no uso do projeto.
- Todas as operações no banco utilizam **prepared statements**, evitando injeção de SQL.
- Conexões são gerenciadas com **pool**, otimizando desempenho e evitando sobrecarga no banco.

---

## 📊 Resultados Esperados

Com o projeto ativo, espera-se:

- Diminuição de erros humanos na digitação de pedidos.
- Acesso a dados mais completos e atualizados.
- Otimização do tempo das equipes operacionais.

---

## 🛠️ Manutenção

O código é modularizado e pode ser adaptado facilmente em caso de mudanças no formato da API, alterações no banco de dados ou regras de negócio. Todas as funções seguem boas práticas de logging e tratamento de erros para facilitar o suporte técnico.

---

> Projeto desenvolvido e mantido pela equipe de Supply e Dados
