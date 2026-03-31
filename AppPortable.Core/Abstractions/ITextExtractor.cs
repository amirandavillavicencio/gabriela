using AppPortable.Core.Models;

namespace AppPortable.Core.Abstractions;

public interface ITextExtractor
{
    Task<IReadOnlyList<PageContent>> ExtractAsync(string pdfPath, CancellationToken cancellationToken = default);
}
