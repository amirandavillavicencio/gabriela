using AppPortable.Domain.Models;

namespace AppPortable.Application.Abstractions;

public interface ITextExtractor
{
    Task<IReadOnlyList<PageContent>> ExtractAsync(string pdfPath, CancellationToken cancellationToken = default);
}
