using System.Diagnostics;
using AppPortable.Application.Abstractions;

namespace AppPortable.Infrastructure.Processing;

public sealed class TesseractCliOcrEngine(string? executablePath = null, string language = "spa") : IOcrEngine
{
    private readonly string _exe = string.IsNullOrWhiteSpace(executablePath) ? "tesseract" : executablePath;
    private readonly string _language = language;

    public bool IsAvailable => ResolveExecutable(_exe) is not null;

    public async Task<IReadOnlyDictionary<int, (string Text, double? Confidence)>> ExtractByPageAsync(string pdfPath, CancellationToken cancellationToken = default)
    {
        if (!IsAvailable)
        {
            return new Dictionary<int, (string Text, double? Confidence)>();
        }

        var psi = new ProcessStartInfo
        {
            FileName = _exe,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false
        };
        psi.ArgumentList.Add(pdfPath);
        psi.ArgumentList.Add("stdout");
        psi.ArgumentList.Add("-l");
        psi.ArgumentList.Add(_language);

        using var process = Process.Start(psi) ?? throw new InvalidOperationException("No se pudo ejecutar Tesseract.");
        var output = await process.StandardOutput.ReadToEndAsync(cancellationToken);
        var error = await process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException($"OCR falló: {error}");
        }

        var pages = output.Split('\f');
        var result = new Dictionary<int, (string Text, double? Confidence)>();
        for (var i = 0; i < pages.Length; i++)
        {
            var text = pages[i].Trim();
            if (!string.IsNullOrWhiteSpace(text))
            {
                result[i + 1] = (text, null);
            }
        }

        return result;
    }

    private static string? ResolveExecutable(string executable)
    {
        if (File.Exists(executable)) return executable;
        var path = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        foreach (var candidate in path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            var fullPath = Path.Combine(candidate, executable);
            if (File.Exists(fullPath)) return fullPath;
            if (OperatingSystem.IsWindows() && File.Exists($"{fullPath}.exe")) return $"{fullPath}.exe";
        }

        return null;
    }
}
