using AppPortable.Core.Models;

namespace AppPortable.Core.Abstractions;

public interface IChunker
{
    IReadOnlyList<ChunkRecord> CreateChunks(DocumentRecord document, int minChars = 500, int maxChars = 1000, int overlapChars = 120);
}
