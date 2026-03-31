using AppPortable.Domain.Models;

namespace AppPortable.Application.Abstractions;

public interface IJsonStore
{
    Task PersistAsync(DocumentRecord document, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<DocumentRecord>> LoadAllAsync(CancellationToken cancellationToken = default);
}
