const vscode = require('vscode');
const path = require('path');

async function buildRepositoryContext(workspaceRoot) {
  if (!workspaceRoot) {
    return {
      summary: 'No hay una carpeta de trabajo abierta. Abre el proyecto de Python en VS Code para que el chat pueda inspeccionarlo.',
      files: []
    };
  }

  const files = await vscode.workspace.findFiles('**/*', '**/node_modules/**', 40);
  const selectedFiles = [];
  const allowedExtensions = new Set(['.py', '.md', '.txt', '.json', '.yml', '.yaml', '.toml', '.ini']);

  for (const file of files) {
    const ext = path.extname(file.fsPath).toLowerCase();
    if (!allowedExtensions.has(ext)) {
      continue;
    }
    const relativePath = path.relative(workspaceRoot, file.fsPath).replace(/\\/g, '/');
    if (relativePath.startsWith('.git') || relativePath.includes('/.git/')) {
      continue;
    }
    selectedFiles.push(relativePath);
    if (selectedFiles.length >= 20) {
      break;
    }
  }

  const contextParts = [];
  contextParts.push(`Workspace root: ${workspaceRoot}`);
  contextParts.push(`Archivos detectados (${selectedFiles.length}):`);
  contextParts.push(selectedFiles.join('\n'));

  const activeEditor = vscode.window.activeTextEditor;
  if (activeEditor?.document) {
    const activePath = activeEditor.document.uri.fsPath;
    if (activePath.startsWith(workspaceRoot)) {
      const activeRelative = path.relative(workspaceRoot, activePath).replace(/\\/g, '/');
      const activeContent = activeEditor.document.getText();
      contextParts.push(`\nArchivo activo: ${activeRelative}`);
      contextParts.push(activeContent.slice(0, 4000));
    }
  }

  for (const relativePath of selectedFiles) {
    const absolutePath = path.join(workspaceRoot, relativePath);
    try {
      const content = await vscode.workspace.fs.readFile(vscode.Uri.file(absolutePath));
      const text = Buffer.from(content).toString('utf8');
      if (!text || text.includes('\u0000')) {
        continue;
      }
      contextParts.push(`\n===== ${relativePath} =====`);
      contextParts.push(text.slice(0, 2200));
    } catch (error) {
      continue;
    }
  }

  return {
    summary: contextParts.join('\n\n').slice(0, 22000),
    files: selectedFiles
  };
}

function activate(context) {
  const disposable = vscode.commands.registerCommand('kazGptBridge.open', async () => {
    const panel = vscode.window.createWebviewPanel(
      'kazGptBridge',
      'Kaz GPT Bridge',
      vscode.ViewColumn.Beside,
      { enableScripts: true }
    );

    const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
    const repositoryContext = await buildRepositoryContext(workspaceRoot);

    panel.webview.html = `<!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="UTF-8" />
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src https: 'unsafe-inline'; style-src 'unsafe-inline'; connect-src https://js.puter.com https://*; img-src https: data:; font-src https: data:;">
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <style>
          body { font-family: Arial, sans-serif; padding: 16px; background: #1e1e1e; color: #f5f5f5; }
          textarea, select, button { width: 100%; margin-top: 8px; padding: 10px; border-radius: 8px; }
          button { background: #2563eb; color: white; border: none; cursor: pointer; }
          pre { white-space: pre-wrap; background: #0f172a; padding: 12px; border-radius: 8px; overflow-x: auto; }
          .mini { font-size: 12px; opacity: 0.8; margin-top: 8px; }
        </style>
      </head>
      <body>
        <h2>Kaz GPT Bridge</h2>
        <p>Usa modelos GPT desde VS Code con contexto del repositorio.</p>
        <textarea id="prompt" rows="6">Explícame cómo trabajar con este proyecto de Python y qué archivos son más importantes.</textarea>
        <select id="model">
          <option value="openai/gpt-5.1-codex-mini">openai/gpt-5.1-codex-mini</option>
          <option value="openai/gpt-5.1-codex-max">openai/gpt-5.1-codex-max</option>
          <option value="openai/gpt-5.3-codex">openai/gpt-5.3-codex</option>
        </select>
        <button id="run">Enviar</button>
        <p id="status">Esperando...</p>
        <div class="mini" id="contextLabel">Contexto del repositorio cargado.</div>
        <pre id="output">Tu respuesta aparecerá aquí.</pre>
        <script>
          const vscode = acquireVsCodeApi();
          const promptInput = document.getElementById('prompt');
          const modelSelect = document.getElementById('model');
          const runButton = document.getElementById('run');
          const output = document.getElementById('output');
          const status = document.getElementById('status');
          const contextLabel = document.getElementById('contextLabel');
          let repositoryContext = '';
          let puterLoaded = false;

          function checkPuterLoaded() {
            return window.puter && window.puter.ai && typeof window.puter.ai.chat === 'function';
          }

          const puterScript = document.createElement('script');
          puterScript.src = 'https://js.puter.com/v2/';
          puterScript.onload = () => {
            puterLoaded = checkPuterLoaded();
            status.textContent = puterLoaded ? 'Puter cargado.' : 'Puter cargado, pero la función no está disponible.';
          };
          puterScript.onerror = () => {
            status.textContent = 'Error al cargar Puter.';
            output.textContent = 'No se pudo cargar https://js.puter.com/v2/. Revisa la conexión de red o el CSP.';
          };
          document.head.appendChild(puterScript);

          window.addEventListener('message', event => {
            const message = event.data;
            if (message.command === 'setContext') {
              repositoryContext = message.text || '';
              contextLabel.textContent = 'Contexto del repositorio cargado.';
            }
            if (message.command === 'setStatus') {
              status.textContent = message.text || 'Esperando...';
            }
            if (message.command === 'setOutput') {
              output.textContent = message.text || '';
            }
          });

          window.addEventListener('load', () => {
            vscode.postMessage({ command: 'ready' });
          });

          function sendPrompt() {
            const prompt = promptInput.value.trim();
            const model = modelSelect.value;
            if (!prompt) {
              output.textContent = 'Escribe un prompt.';
              return;
            }
            status.textContent = 'Consultando Puter con contexto del repositorio...';
            output.textContent = 'Cargando...';

            if (!puterLoaded) {
              output.textContent = 'Puter aún no está disponible. Espera unos segundos y vuelve a intentar.';
              status.textContent = 'Puter no cargado.';
              return;
            }

            const fullPrompt = 'Tu tarea es ayudar con este proyecto de Python. Usa el contexto del repositorio a continuación para responder la pregunta del usuario.\n\nContexto del repositorio:\n' + repositoryContext + '\n\nPregunta del usuario:\n' + prompt;

            window.puter.ai.chat(fullPrompt, { model })
              .then((response) => {
                output.textContent = typeof response === 'string' ? response : JSON.stringify(response, null, 2);
                status.textContent = 'Respuesta recibida';
              })
              .catch((error) => {
                output.textContent = 'Error: ' + (error && error.message ? error.message : error);
                status.textContent = 'Fallo la solicitud';
              });
          }

          runButton.addEventListener('click', sendPrompt);
          promptInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              sendPrompt();
            }
          });
        </script>
      </body>
      </html>`;

    panel.webview.postMessage({ command: 'setContext', text: repositoryContext.summary });
  });

  context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = { activate, deactivate };
