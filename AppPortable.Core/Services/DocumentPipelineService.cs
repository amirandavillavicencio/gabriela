using System.Security.Cryptography;
using System.Text;
using AppPortable.Core.Abstractions;
using AppPortable.Core.Models;

namespace AppPortable.Core.Services;

public sealed class DocumentPipelineService(
    ITextExtractor textExtractor,
    IOcrEngine ocrEngine,
    IChunker chunker,
    IJsonStore jsonStore,
    IIndexer indexer)
{
    public async Task<DocumentRecord> ProcessAsync(string pdfPath, ProcessingOptions? options = null, CancellationToken cancellationToken = default)
    {
        options ??= new ProcessingOptions();
        if (!File.Exists(pdfPath)) throw new FileNotFoundException("No existe el PDF", pdfPath);

        var pages = (await textExtractor.ExtractAsync(pdfPath, cancellationToken)).Select(ClonePage).ToList();
        var ocrByPage = new Dictionary<int, (string Text, double? Confidence)>();
        if (ocrEngine.IsAvailable && (options.ForceOcr || pages.Any(p => !TextIsUseful(p.Text))))
        {
            foreach (var pair in await ocrEngine.ExtractByPageAsync(pdfPath, cancellationToken))
            {
                ocrByPage[pair.Key] = pair.Value;
            }
        }

        var nativePages = 0;
        var ocrPages = 0;
        foreach (var page in pages)
        {
            var nativeUseful = TextIsUseful(page.Text);
            var ocrFound = ocrByPage.TryGetValue(page.PageNumber, out var ocr);
            var ocrUseful = ocrFound && TextIsUseful(ocr.Text);

            if (!options.ForceOcr && nativeUseful)
            {
                page.ExtractionLayer = ExtractionLayer.Native;
                nativePages++;
                continue;
            }

            if (ocrUseful)
            {
                page.Text = Normalize(ocr.Text);
                page.OcrConfidence = ocr.Confidence;
                page.ExtractionLayer = nativeUseful ? ExtractionLayer.Mixed : ExtractionLayer.Ocr;
                ocrPages++;
                continue;
            }

            page.ExtractionLayer = nativeUseful ? ExtractionLayer.Native : ExtractionLayer.Fallback;
            if (nativeUseful) nativePages++;
            else page.Warnings.Add("sin_texto_util");
        }

        var doc = new DocumentRecord
        {
            DocumentId = BuildDocumentId(pdfPath),
            SourceFile = Path.GetFileName(pdfPath),
            SourcePath = Path.GetFullPath(pdfPath),
            ProcessedAtUtc = DateTime.UtcNow,
            TotalPages = pages.Count,
            Pages = pages,
            Warnings = pages.Where(p => p.Warnings.Count > 0).SelectMany(p => p.Warnings).Distinct().ToList(),
            ExtractionSummary = new ExtractionSummary
            {
                OcrEnabled = true,
                OcrAvailable = ocrEngine.IsAvailable,
                OcrUsed = ocrPages > 0,
                OcrPages = ocrPages,
                NativePages = nativePages,
                HasExtractableText = pages.Any(p => TextIsUseful(p.Text))
            }
        };

        doc.Chunks = chunker.CreateChunks(doc, options.MinChunkChars, options.MaxChunkChars, options.OverlapChars).ToList();
        await jsonStore.PersistAsync(doc, cancellationToken);
        await indexer.IndexDocumentAsync(doc, cancellationToken);
        return doc;
    }

    public Task<IReadOnlyList<SearchResultRecord>> SearchAsync(string query, int limit = 20, CancellationToken cancellationToken = default)
        => indexer.SearchAsync(query, limit, cancellationToken);

    private static bool TextIsUseful(string text)
    {
        var cleaned = Normalize(text);
        if (cleaned.Length < 60) return false;
        var words = cleaned.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return words.Length >= 10;
    }

    private static string Normalize(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return string.Empty;
        var compact = text.Replace("\r", "\n");
        compact = string.Join('\n', compact.Split('\n').Select(s => s.Trim()).Where(s => !string.IsNullOrWhiteSpace(s)));
        return compact;
    }

    private static string BuildDocumentId(string path)
    {
        using var sha = SHA256.Create();
        var hash = Convert.ToHexString(sha.ComputeHash(File.ReadAllBytes(path))).ToLowerInvariant();
        var stem = Path.GetFileNameWithoutExtension(path).ToLowerInvariant().Replace(' ', '_');
        return $"doc_{stem}_{hash[..12]}";
    }

    private static PageContent ClonePage(PageContent source) => new()
    {
        PageNumber = source.PageNumber,
        Text = Normalize(source.Text),
        ExtractionLayer = source.ExtractionLayer,
        OcrConfidence = source.OcrConfidence,
        Warnings = [.. source.Warnings]
    };
}
