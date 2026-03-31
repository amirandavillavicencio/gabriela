using AppPortable.Domain.Models;

namespace AppPortable.Application.Abstractions;

public interface IChunker
{
    IReadOnlyList<ChunkRecord> CreateChunks(DocumentRecord document, int minChars = 500, int maxChars = 1000, int overlapChars = 120);
}
