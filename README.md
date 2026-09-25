# Logistics Automation Hub

> Plataforma local para gestão, automação e rastreabilidade de operações logísticas.

**B.A Dev Lab — Desenvolvimento • Automação • Tecnologia**

![Version](https://img.shields.io/badge/version-1.1%20Stable-8B2BE2)
![Python](https://img.shields.io/badge/Python-3.x-2457E6)
![Flask](https://img.shields.io/badge/Flask-Backend-D414C8)
![SQLite](https://img.shields.io/badge/SQLite-Database-2457E6)
![Status](https://img.shields.io/badge/status-Stable-22C55E)

---

## Sobre o projeto

O **Logistics Automation Hub** é uma aplicação desenvolvida para centralizar e estruturar operações logísticas em um fluxo rastreável.

O projeto integra entrada e validação de dados, cadastros operacionais, acompanhamento de operações, gerenciamento de docas, alertas, indicadores, histórico e relatórios em uma única aplicação.

A proposta nasceu da necessidade de transformar processos que normalmente dependem de planilhas e controles descentralizados em um fluxo operacional estruturado, sem eliminar a decisão humana em situações ambíguas.

A versão **1.1 Stable** é distribuída como aplicação local para Windows e utiliza SQLite para persistência dos dados.

---

## Principais funcionalidades

### Operations Core

Centraliza as operações e atribui a cada registro um identificador imutável no padrão:

```text
OP-000001
```

As operações podem ser originadas por:

- cadastro manual;
- planilhas validadas;
- arquivos JSON, XML ou TXT;
- futuras integrações com APIs, TMS ou WMS.

Informações inexistentes na origem não são preenchidas automaticamente.

---

### Workflow operacional

Cada operação percorre um fluxo controlado:

```text
AGUARDANDO
    ↓
NO PÁTIO
    ↓
EM OPERAÇÃO
    ↓
FINALIZADO
    ↓
CONCLUÍDA
```

Também existe suporte ao status `CANCELADO`.

As mudanças registram evento, usuário, data/hora e transição de status, permitindo rastreabilidade da operação.

---

### Cadastros operacionais

O sistema possui cadastros persistentes para:

- transportadoras;
- motoristas;
- veículos;
- docas.

Esses registros podem ser reutilizados na criação das operações.

O sistema também possui tratamento de registros legados para auxiliar na organização de informações provenientes de operações anteriores aos cadastros estruturados.

---

### Validação de planilhas

Planilhas podem ser analisadas antes de gerar operações.

A aplicação prioriza a revisão humana:

> A repetição isolada de placa, motorista ou documento não caracteriza automaticamente uma operação duplicada.

Casos ambíguos permanecem disponíveis para revisão em vez de serem removidos ou alterados automaticamente.

---

### Central Operacional

Painel para acompanhamento das operações ativas, incluindo:

- operações em andamento;
- situação das docas;
- indicadores operacionais;
- alertas;
- acompanhamento do fluxo.

O sistema impede o início simultâneo de duas operações na mesma doca.

---

### Alertas operacionais

O Hub acompanha tempos operacionais e pode gerar alertas relacionados a:

- tempo de espera;
- duração da operação;
- permanência total.

Os limites podem ser configurados dentro da aplicação.

---

### Relatórios

A área de relatórios permite consultas utilizando filtros como:

- período;
- status;
- transportadora;
- motorista;
- placa;
- doca.

Também são calculados indicadores como:

- tempo médio de espera;
- tempo médio de operação;
- tempo médio de permanência.

Os resultados podem ser exportados em CSV.

---

### Histórico e rastreabilidade

Eventos e alterações importantes permanecem registrados no banco SQLite, permitindo acompanhar a evolução das operações e dos processamentos realizados pelo sistema.

---

## Arquitetura

```text
┌───────────────────────────────┐
│         Interface Web         │
│      HTML • CSS • JS          │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│          Flask API            │
│            Python             │
└───────────────┬───────────────┘
                │
        ┌───────┴─────────┐
        ▼                 ▼
┌──────────────┐   ┌──────────────┐
│    SQLite    │   │ Pandas /     │
│ Persistência │   │ OpenPyXL     │
└──────────────┘   └──────────────┘
```

---

## Tecnologias

| Tecnologia | Utilização |
|---|---|
| Python | Backend e regras de negócio |
| Flask | API e servidor local |
| SQLite | Persistência |
| Pandas | Processamento de dados |
| OpenPyXL | Manipulação de planilhas |
| HTML5 | Interface |
| CSS3 | Design e responsividade |
| JavaScript | Interações e consumo da API |
| PyInstaller | Build da aplicação Windows |
| Inno Setup | Instalador Windows |

---

## Estrutura do projeto

```text
logistics-automation-hub/
│
├── assets/
├── config/
├── css/
├── data/
├── docs/
├── js/
├── python/
│   ├── app.py
│   └── database.py
│
├── index.html
├── LogisticsAutomationHub.spec
├── requirements.txt
├── .gitignore
└── README.md
```

Arquivos de banco, logs, ambientes virtuais e artefatos de distribuição não fazem parte do código versionado.

---

## Executando em ambiente de desenvolvimento

### 1. Clone o repositório

```bash
git clone SEU_LINK_DO_REPOSITORIO
cd logistic-automation-hub
```

### 2. Crie o ambiente virtual

```bash
python -m venv .venv
```

### 3. Ative o ambiente

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instale as dependências

```bash
pip install -r requirements.txt
```

### 5. Execute

```bash
python python/app.py
```

A aplicação será disponibilizada localmente em:

```text
http://127.0.0.1:5000
```

Na primeira execução, o sistema cria sua estrutura persistente e permite configurar o primeiro usuário.

---

## Gerando o build Windows

Com as dependências de desenvolvimento instaladas:

```bash
pyinstaller LogisticsAutomationHub.spec
```

O build será gerado em:

```text
dist/LogisticsAutomationHub/
```

> Os arquivos de `dist/` e `build/` não são versionados no repositório.

---

## Versão pronta para Windows

Para quem deseja apenas testar a aplicação sem configurar o ambiente Python, a versão compilada está disponível na área de **Releases** deste repositório.

### V1.1 Stable

A distribuição Windows utiliza:

```text
PyInstaller → aplicação
Inno Setup  → instalador
```

Os dados da aplicação são mantidos separadamente da instalação em:

```text
%LOCALAPPDATA%\BA Dev Lab\Logistics Automation Hub
```

Isso permite atualizar ou reinstalar a aplicação sem utilizar a pasta do programa como armazenamento operacional.

---

## Screenshots

> As imagens da versão V1.1 Stable serão adicionadas nesta seção.

### Operations Core

`Screenshot em preparação`

### Central Operacional

`Screenshot em preparação`

### Validação de Planilhas

`Screenshot em preparação`

### Relatórios

`Screenshot em preparação`

---

## Princípios do projeto

Algumas decisões importantes da arquitetura:

- dados ausentes não são inventados;
- repetição isolada não significa duplicidade;
- situações ambíguas são encaminhadas para revisão humana;
- alterações operacionais relevantes são rastreáveis;
- dados persistentes ficam separados dos arquivos da aplicação;
- código-fonte e artefatos de distribuição são mantidos separadamente.

---

## Roadmap

A V1.1 representa a primeira versão Stable da arquitetura atual.

Evoluções futuras podem incluir:

- interface desktop própria;
- integrações com TMS/WMS;
- APIs externas;
- novos indicadores operacionais;
- expansão dos mecanismos de integração e automação.

---

## Autor

**Bruno Ribeiro**

B.A Dev Lab  
**Desenvolvimento • Automação • Tecnologia**

---

## Status

**V1.1 Stable — Homologada**

Projeto em evolução dentro do portfólio **B.A Dev Lab**.