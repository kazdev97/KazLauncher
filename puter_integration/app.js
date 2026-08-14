const puter = window.puter;
const promptInput = document.getElementById('prompt');
const modelSelect = document.getElementById('model');
const runButton = document.getElementById('run');
const output = document.getElementById('output');
const status = document.getElementById('status');

if (!puter?.ai?.chat) {
  status.textContent = 'Puter no está cargado. Revisa la conexión a internet.';
  output.textContent = 'No se pudo inicializar Puter.';
} else {
  runButton.addEventListener('click', async () => {
    const prompt = promptInput.value.trim();
    const model = modelSelect.value;

    if (!prompt) {
      output.textContent = 'Escribe un prompt antes de continuar.';
      return;
    }

    status.textContent = 'Solicitando respuesta desde Puter...';
    output.textContent = 'Cargando...';

    try {
      const response = await puter.ai.chat(prompt, { model });
      const text = typeof response === 'string' ? response : JSON.stringify(response, null, 2);
      output.textContent = text;
      status.textContent = `Respuesta recibida con ${model}`;
    } catch (error) {
      output.textContent = `Error: ${error?.message || error}`;
      status.textContent = 'No se pudo completar la solicitud.';
    }
  });
}
