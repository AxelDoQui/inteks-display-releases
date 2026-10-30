// InTeks Display — el panel de administración como app de escritorio.
//
// Una ventana propia con WebView2 (el motor de Edge que ya trae Windows 10/11)
// en lugar de `chrome.exe --app=...`. La diferencia que importa: este programa
// tiene su propio .exe, su icono y su identidad de barra de tareas, así que al
// anclarlo se ancla "InTeks Display" y no "Chrome".
//
// Hace lo mismo que abrir-panel.bat: mira si el servidor escucha, lo despierta
// con la tarea programada si no, y abre /admin.html. Se compila con csc.exe
// (C# 5, el que trae Windows): nada de interpolación de cadenas ni de `?.`.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

static class Programa
{
    [DllImport("shell32.dll")]
    static extern void SetCurrentProcessExplicitAppUserModelID(
        [MarshalAs(UnmanagedType.LPWStr)] string id);

    // Relanza la pantalla y cierra esta instancia. Hay que esperar unos segundos:
    // mientras esta siga viva tiene el mutex, y la nueva se iría por «ya hay una».
    public static void Reiniciar()
    {
        try
        {
            var psi = new ProcessStartInfo("cmd.exe",
                "/c timeout /t 4 /nobreak >nul & start \"\" \"" + Application.ExecutablePath + "\" --pantalla");
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            Process.Start(psi);
        }
        catch { }
        Environment.Exit(1);
    }

    // El ajuste «Este PC reproduce en su propia pantalla» del panel. Solo un
    // `"pantalla_pc": false` explícito lo apaga: ausente, ilegible o cualquier
    // otra cosa cuenta como activo, porque un error de lectura nunca debe dejar
    // un televisor en negro.
    public static bool LeerPantallaPc(string json)
    {
        try { return !Regex.IsMatch(json ?? "", "\"pantalla_pc\"\\s*:\\s*false"); }
        catch { return true; }
    }

    // La misma config que lee Ventana.Puertos(): la de la carpeta de datos manda
    // y la de junto al .exe es solo la plantilla del instalador.
    public static bool PantallaActiva()
    {
        try
        {
            string cfg = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "InTeks Display", "config.json");
            if (!File.Exists(cfg))
                cfg = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");
            return LeerPantallaPc(File.ReadAllText(cfg));
        }
        catch { return true; }
    }

    // Sin argumentos: el panel de administración. Con --pantalla: este equipo ES
    // una pantalla (el mini PC pegado al televisor) y reproduce a pantalla
    // completa, sin marco, sin cursor y sin atajos del navegador.
    [STAThread]
    static void Main(string[] args)
    {
        bool pantalla = Array.IndexOf(args, "--pantalla") >= 0;
        if (pantalla)
        {
            // Cualquier error sin controlar: volver a arrancar en vez de quedarse
            // con un cuadro de error encima del escaparate.
            Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
            Application.ThreadException += delegate { Reiniciar(); };
            AppDomain.CurrentDomain.UnhandledException += delegate { Reiniciar(); };
        }
        // Antes de crear ninguna ventana: es lo que separa este icono del de Chrome.
        SetCurrentProcessExplicitAppUserModelID(pantalla ? "InTeks.Display.Pantalla" : "InTeks.Display.Panel");
        bool primera;
        using (var m = new Mutex(true, pantalla ? "InTeksDisplayPantalla" : "InTeksDisplayPanel", out primera))
        {
            if (!primera) return;      // ya hay una abierta
            // Apagada desde el panel: la tarea programada sigue llamando cada
            // 5 minutos, pero aquí se queda en nada.
            if (pantalla && !PantallaActiva()) return;
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new Ventana(pantalla));
        }
    }
}

class Ventana : Form
{
    readonly WebView2 web = new WebView2();
    readonly Label aviso = new Label();
    readonly Button reintentar = new Button();
    readonly bool pantalla;
    int puerto;

    public Ventana(bool pantalla)
    {
        this.pantalla = pantalla;
        Text = "InTeks Display";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        StartPosition = FormStartPosition.CenterScreen;
        var area = Screen.PrimaryScreen.WorkingArea;
        Size = new Size(Math.Min(1366, area.Width - 40), Math.Min(850, area.Height - 40));
        MinimumSize = new Size(900, 600);
        BackColor = Color.FromArgb(15, 17, 23);
        if (pantalla)
        {
            // Pantalla completa de verdad: sin marco ni barra de tareas encima.
            FormBorderStyle = FormBorderStyle.None;
            WindowState = FormWindowState.Maximized;
            BackColor = Color.Black;
            Cursor.Hide();
            // Si se apaga el ajuste con la pantalla abierta, se cierra sola.
            var vigia = new System.Windows.Forms.Timer { Interval = 5000 };
            vigia.Tick += delegate { if (!Programa.PantallaActiva()) { vigia.Stop(); Close(); } };
            vigia.Start();
        }

        aviso.Dock = DockStyle.Fill;
        aviso.TextAlign = ContentAlignment.MiddleCenter;
        aviso.ForeColor = Color.White;
        aviso.Font = new Font("Segoe UI", 12f);
        aviso.Text = "Iniciando InTeks Display…";

        reintentar.Text = "Reintentar";
        reintentar.Size = new Size(120, 34);
        reintentar.Visible = false;
        reintentar.Anchor = AnchorStyles.None;
        reintentar.Click += delegate { Arrancar(); };

        web.Dock = DockStyle.Fill;
        web.Visible = false;

        Controls.Add(web);
        Controls.Add(reintentar);
        Controls.Add(aviso);
        Resize += delegate { Centrar(); };
        Shown += delegate { Arrancar(); };
    }

    void Centrar()
    {
        reintentar.Left = (ClientSize.Width - reintentar.Width) / 2;
        reintentar.Top = ClientSize.Height / 2 + 40;
    }

    // ── Servidor ────────────────────────────────────────────────────────────
    // La que manda es la config de la carpeta de datos; la de junto al .exe es
    // solo la plantilla del instalador (igual que en abrir-panel.bat).
    static int[] Puertos()
    {
        string cfg = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
            "InTeks Display", "config.json");
        if (!File.Exists(cfg))
            cfg = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");
        int p = 80, f = 9000;
        try
        {
            string t = File.ReadAllText(cfg);
            Match m = Regex.Match(t, "\"port\"\\s*:\\s*(\\d+)");
            if (m.Success) p = int.Parse(m.Groups[1].Value);
            m = Regex.Match(t, "\"port_fallback\"\\s*:\\s*(\\d+)");
            if (m.Success) f = int.Parse(m.Groups[1].Value);
        }
        catch { }
        return new int[] { p, f };
    }

    static bool Escucha(int puerto)
    {
        try
        {
            using (var c = new TcpClient())
            {
                IAsyncResult r = c.BeginConnect("127.0.0.1", puerto, null, null);
                if (!r.AsyncWaitHandle.WaitOne(400)) return false;
                c.EndConnect(r);
                return true;
            }
        }
        catch { return false; }
    }

    static int Buscar()
    {
        foreach (int p in Puertos()) if (Escucha(p)) return p;
        return 0;
    }

    void Arrancar()
    {
        reintentar.Visible = false;
        aviso.Visible = true;
        aviso.Text = "Iniciando InTeks Display…";
        new Thread(delegate ()
        {
            int p = Buscar();
            if (p == 0)
            {
                // Despertar la tarea programada que mantiene el servidor.
                try
                {
                    var psi = new ProcessStartInfo("schtasks", "/Run /TN \"InTeks Display\"");
                    psi.CreateNoWindow = true;
                    psi.UseShellExecute = false;
                    Process.Start(psi);
                }
                catch { }
                // Una pantalla no se rinde: tras un corte de luz el servidor
                // tarda más que el reproductor en estar listo, y nadie va a
                // pulsar «Reintentar» en un televisor.
                for (int i = 0; (pantalla || i < 30) && p == 0; i++) { Thread.Sleep(1000); p = Buscar(); }
            }
            try { BeginInvoke(new Action(delegate { Listo(p); })); } catch { }
        }) { IsBackground = true }.Start();
    }

    async void Listo(int p)
    {
        if (p == 0)
        {
            aviso.Text = "El servidor no responde.\n\nComprueba la tarea programada «InTeks Display»\n"
                + "y el registro en %ProgramData%\\InTeks Display\\server.log";
            reintentar.Visible = true;
            Centrar();
            return;
        }
        puerto = p;
        try
        {
            string datos = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "InTeks Display", "webview");
            // La pantalla guarda su identidad (el nombre con el que se emparejó)
            // en su propio almacén, separado del del panel.
            if (pantalla) datos += "-pantalla";
            // Sin esto los vídeos con sonido no arrancan solos.
            var opciones = new CoreWebView2EnvironmentOptions("--autoplay-policy=no-user-gesture-required");
            var entorno = await CoreWebView2Environment.CreateAsync(null, datos, opciones);
            await web.EnsureCoreWebView2Async(entorno);
            if (pantalla)
            {
                var aj = web.CoreWebView2.Settings;
                aj.AreBrowserAcceleratorKeysEnabled = false;
                aj.AreDefaultContextMenusEnabled = false;
                aj.AreDevToolsEnabled = false;
                aj.IsStatusBarEnabled = false;
                aj.IsZoomControlEnabled = false;
                // El cursor desaparece también sobre el contenido.
                await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(
                    "document.addEventListener('DOMContentLoaded',function(){var s=document.createElement('style');"
                    + "s.textContent='*{cursor:none!important}';document.head.appendChild(s);});");
            }
            web.CoreWebView2.NewWindowRequested += delegate (object s, CoreWebView2NewWindowRequestedEventArgs e)
            {
                e.Handled = true;          // nada de ventanas sueltas: al navegador
                AbrirFuera(e.Uri);
            };
            web.CoreWebView2.NavigationStarting += delegate (object s, CoreWebView2NavigationStartingEventArgs e)
            {
                Uri u;
                if (Uri.TryCreate(e.Uri, UriKind.Absolute, out u) && !EsLocal(u))
                {
                    e.Cancel = true;
                    AbrirFuera(e.Uri);
                }
            };
            web.CoreWebView2.DocumentTitleChanged += delegate { Text = "InTeks Display"; };
            if (pantalla)
            {
                // Un televisor sin nadie delante tiene que arreglarse solo.
                web.CoreWebView2.ProcessFailed += delegate (object s, CoreWebView2ProcessFailedEventArgs e)
                {
                    if (e.ProcessFailedKind == CoreWebView2ProcessFailedKind.BrowserProcessExited)
                        Programa.Reiniciar();                 // se cayó todo el motor
                    else
                        BeginInvoke(new Action(delegate { web.Reload(); }));   // un proceso de página
                };
                // Si la página no carga (el servidor aún arranca, o se reinició),
                // se vuelve a pedir en 5 s en vez de dejar el error en pantalla.
                web.NavigationCompleted += delegate (object s, CoreWebView2NavigationCompletedEventArgs e)
                {
                    if (e.IsSuccess) return;
                    var t = new System.Windows.Forms.Timer { Interval = 5000 };
                    t.Tick += delegate { t.Stop(); t.Dispose(); web.Reload(); };
                    t.Start();
                };
            }
            // La raíz es el router de pantallas: si ya está emparejada abre su
            // player; si no, pide el PIN en /pair (una sola vez).
            web.Source = new Uri("http://localhost:" + puerto + (pantalla ? "/" : "/admin.html"));
            web.Visible = true;
            aviso.Visible = false;
        }
        catch (Exception ex)
        {
            aviso.Text = "No se pudo abrir el panel.\n\nFalta el componente WebView2 de Microsoft\n"
                + "(viene con Windows 10 y 11 actualizados).\n\n" + ex.Message;
        }
    }

    static bool EsLocal(Uri u)
    {
        if (u.Scheme != "http" && u.Scheme != "https") return true;   // about:blank, data:...
        string h = u.Host;
        return h == "localhost" || h == "127.0.0.1" || h == "::1" || h == "[::1]";
    }

    static void AbrirFuera(string url)
    {
        Uri u;
        // Solo http(s): un esquema raro no se lanza en el sistema.
        if (!Uri.TryCreate(url, UriKind.Absolute, out u)) return;
        if (u.Scheme != "http" && u.Scheme != "https") return;
        try { Process.Start(new ProcessStartInfo(u.AbsoluteUri) { UseShellExecute = true }); }
        catch { }
    }
}
