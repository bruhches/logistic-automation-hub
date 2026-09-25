# Logistics Automation Hub — V1.0

Primeiro release candidato do módulo **Spreadsheet Automation**. A V1.0 consolida as funcionalidades homologadas até a V0.9 e faz o acabamento de experiência antes do primeiro empacotamento com PyInstaller.

## Fluxo principal
1. Login local.
2. Configuração das regras operacionais.
3. Upload e análise de `.xlsx`/`.xlsm`.
4. Revisão humana com busca, filtros, comparação e ações seguras em lote.
5. Geração do XLSX tratado.
6. Auditoria por `PROC ID`, `HUB ID`, SQLite e rastreabilidade no arquivo final.

## Ajustes de V1.0
- interface reorganizada na ordem real de operação;
- guia visual em quatro etapas;
- textos e botões mais orientados à ação;
- feedback visual, foco de teclado e responsividade refinados;
- aviso explícito quando ainda existem ocorrências em `Revisar`;
- confirmação antes de finalizar com pendências;
- regras deixam claro que passam a valer na próxima análise;
- backend identificado como V1.0 e execução sem `debug`, preparando o build desktop.

## Executar para homologação
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python python/app.py
```
Abra `http://127.0.0.1:5000`.

Após a homologação funcional da V1.0, o próximo passo é criar o primeiro build experimental para Windows com PyInstaller.


## Build Windows - V1.0
A distribuição PyInstaller separa recursos do programa dos dados mutáveis. Quando executado como EXE, banco SQLite, regras, logs, entradas e saídas ficam em `%LOCALAPPDATA%\LogisticsAutomationHub`. Em uma instalação realmente nova, `usuarios = 0` abre a tela **Configuração inicial** para criação do primeiro operador.

Build de diagnóstico recomendado (PowerShell na raiz, `.venv` ativa):
```powershell
pyinstaller --noconfirm --clean --onedir --console --name "LogisticsAutomationHub" --add-data "index.html;." --add-data "css;css" --add-data "js;js" --add-data "assets;assets" --add-data "config;config" --paths "python" .\python\app.py
```
Antes de testar, confirme que não existe outro servidor usando a porta 5000. Para simular uma primeira instalação após testes anteriores, renomeie (não apague, se quiser preservar) `%LOCALAPPDATA%\LogisticsAutomationHub`.


## Windows Build 2
- Abre automaticamente o navegador padrão em http://127.0.0.1:5000 ao iniciar.
- Mantém persistência em %LOCALAPPDATA%\LogisticsAutomationHub.
- Para o primeiro teste, compile com --console; após homologação, use --windowed.


## Windows Build 3 — modo gráfico
- Mantém o comportamento homologado do Build 2.
- Compatível com PyInstaller `--windowed`, sem janela de console.
- O navegador padrão continua abrindo automaticamente.
- Persistência continua em `%LOCALAPPDATA%\LogisticsAutomationHub`.

Build recomendado:
```powershell
pyinstaller --noconfirm --clean --onedir --windowed --name "LogisticsAutomationHub" --add-data "index.html;." --add-data "css;css" --add-data "js;js" --add-data "assets;assets" --add-data "config;config" --paths "python" .\python\app.py
```

## V1.0 Release Candidate 1 — B.A Dev Lab

Esta versão prepara a distribuição final no Windows sem alterar o motor funcional homologado.

- Identidade do fabricante: **B.A Dev Lab**.
- Ícone Windows: `assets/branding/BA-Dev-Lab.ico`.
- Favicon da interface incluído.
- Dados persistentes do EXE: `%LOCALAPPDATA%\BA Dev Lab\Logistics Automation Hub`.
- Migração conservadora: se a nova pasta ainda não existir e `%LOCALAPPDATA%\LogisticsAutomationHub` existir, os dados do Build 3 são **copiados** para a nova estrutura. O diretório antigo não é apagado.

### Compilação RC1

```powershell
pyinstaller --noconfirm --clean --onedir --windowed --name "LogisticsAutomationHub" --icon "assets\branding\BA-Dev-Lab.ico" --add-data "index.html;." --add-data "css;css" --add-data "js;js" --add-data "assets;assets" --add-data "config;config" --paths "python" .\python\app.py
```

### Teste de homologação

1. Abrir o EXE e confirmar abertura automática no navegador, sem console.
2. Confirmar que usuário e histórico do Build 3 foram preservados na máquina já testada.
3. Em uma máquina/usuário Windows sem dados anteriores, confirmar a tela de Configuração inicial.
4. Processar a planilha de homologação, tomar decisões, gerar XLSX e conferir Histórico.
5. Fechar e reabrir o EXE e confirmar persistência.
6. Confirmar o ícone B.A Dev Lab no executável.
