using System.Text.Json;
using AppPortable.Core.Abstractions;
using AppPortable.Core.Models;

namespace AppPortable.Infrastructure.Persistence;

public sealed class JsonFileStore(AppPaths paths) : IJsonStore
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public Task PersistAsync(DocumentRecord document, CancellationToken cancellationToken = default)
    {
        paths.EnsureAll();
        var docDir = Path.Combine(paths.Documents, document.DocumentId);
        var extracted = Path.Combine(docDir, "extracted");
        Directory.CreateDirectory(extracted);

        File.WriteAllText(Path.Combine(extracted, "document.json"), JsonSerializer.Serialize(document, JsonOptions));
        File.WriteAllText(Path.Combine(extracted, "pages.json"), JsonSerializer.Serialize(document.Pages, JsonOptions));
        File.WriteAllText(Path.Combine(extracted, "chunks.json"), JsonSerializer.Serialize(document.Chunks, JsonOptions));
        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<DocumentRecord>> LoadAllAsync(CancellationToken cancellationToken = default)
    {
        paths.EnsureAll();
        var list = new List<DocumentRecord>();
        foreach (var file in Directory.EnumerateFiles(paths.Documents, "document.json", SearchOption.AllDirectories))
        {
            var content = File.ReadAllText(file);
            var doc = JsonSerializer.Deserialize<DocumentRecord>(content);
            if (doc is not null) list.Add(doc);
        }

        return Task.FromResult<IReadOnlyList<DocumentRecord>>(list);
    }
}
