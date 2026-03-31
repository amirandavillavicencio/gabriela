using AppPortable.Core.Models;

namespace AppPortable.Core.Abstractions;

public interface IJsonStore
{
    Task PersistAsync(DocumentRecord document, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<DocumentRecord>> LoadAllAsync(CancellationToken cancellationToken = default);
}
