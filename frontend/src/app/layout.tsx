import "./globals.css";
import TelemetryBar from "./TelemetryBar";
import AppSidebar from "./components/AppSidebar";
import { ThemeProvider } from "./theme-provider";

export const metadata = {
  title: "EEFN | Exoplanet Evidence Fusion Network",
  description: "A scientific evidence intelligence platform for exoplanet validation.",
};

// Runs before paint (blocking, inline) so the stored theme applies immediately --
// without this, the page would flash the default theme before ThemeProvider's
// useEffect runs on the client.
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = window.localStorage.getItem("eefn-theme");
    if (stored && stored !== "system") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <AppSidebar />
          <div className="app-frame">
            <TelemetryBar />
            <main className="app-main">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
