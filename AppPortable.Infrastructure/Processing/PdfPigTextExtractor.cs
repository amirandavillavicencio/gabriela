using AppPortable.Core.Abstractions;
using AppPortable.Core.Models;
using UglyToad.PdfPig;

namespace AppPortable.Infrastructure.Processing;

public sealed class PdfPigTextExtractor : ITextExtractor
{
    public Task<IReadOnlyList<PageContent>> ExtractAsync(string pdfPath, CancellationToken cancellationToken = default)
    {
        var pages = new List<PageContent>();
        using var document = PdfDocument.Open(pdfPath);
        foreach (var page in document.GetPages())
        {
            cancellationToken.ThrowIfCancellationRequested();
            pages.Add(new PageContent
            {
                PageNumber = page.Number,
                Text = page.Text,
                ExtractionLayer = ExtractionLayer.Native
            });
        }

        return Task.FromResult<IReadOnlyList<PageContent>>(pages);
    }
}
