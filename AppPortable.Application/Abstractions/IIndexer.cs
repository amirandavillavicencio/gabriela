using AppPortable.Domain.Models;

namespace AppPortable.Application.Abstractions;

public interface IIndexer
{
    Task IndexDocumentAsync(DocumentRecord document, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<SearchResultRecord>> SearchAsync(string query, int limit = 20, CancellationToken cancellationToken = default);
}
