# Firma digital — KazLauncher

## Autofirma (prueba gratuita)

Sirve para ver **cómo se comporta Windows** con un ejecutable firmado, **no** para quitar SmartScreen en la mayoría de PCs.

### Requisitos

- **Windows SDK** (incluye `signtool.exe`): instalar desde Visual Studio → *Windows SDK*, o desde [Windows SDK](https://developer.microsoft.com/windows/downloads/windows-sdk/).

### Pasos

```powershell
# 1) Crear certificado autofirmado (solo una vez)
.\packaging\selfsign\create_cert.ps1

# 2) Compilar el launcher
.\packaging\build_release.ps1

# 3) Firmar dist\KazLauncher.exe
.\packaging\selfsign\sign_exe.ps1

# 4) Opcional: confiar el cert SOLO en tu PC (prueba local)
.\packaging\selfsign\trust_local.ps1
```

Contraseña por defecto del PFX: `KazSelfSign2026!`  
(Puedes usar `$env:KAZ_SELFSIGN_PASSWORD = "otra"`.)

### Qué deberías ver

| Situación | Resultado esperado |
|-----------|-------------------|
| Propiedades → Firmas digitales | Editor **Soy Kaz** |
| `Get-AuthenticodeSignature` | `UnknownError` o `NotTrusted` sin `trust_local` |
| SmartScreen en PC limpio | **Sigue avisando** ("Editor desconocido") |
| SmartScreen tras `trust_local.ps1` | Puede mejorar **solo en tu PC**; no es garantía |
| Otros usuarios | Sin cambio; necesitan certificado de CA |

### Quitar confianza local

```powershell
.\packaging\selfsign\trust_local.ps1 -Remove
```

---

## Firma real (producción)

Para reducir SmartScreen de forma fiable hace falta un **certificado de firma de código** emitido por una CA (OV o EV), por ejemplo DigiCert, Sectigo, SSL.com.

```powershell
$env:KAZ_SIGN_PFX = "C:\ruta\SoyKaz.pfx"
$env:KAZ_SIGN_PASSWORD = "contraseña"
.\packaging\sign_release.ps1
```

Los archivos `*.pfx` están en `.gitignore` — **nunca subirlos al repositorio**.
