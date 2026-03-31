namespace AppPortable.Domain.Models;

public sealed class SearchResultRecord
{
    public string ChunkId { get; set; } = string.Empty;
    public string DocumentId { get; set; } = string.Empty;
    public string SourceFile { get; set; } = string.Empty;
    public int PageStart { get; set; }
    public int PageEnd { get; set; }
    public int ChunkIndex { get; set; }
    public string Snippet { get; set; } = string.Empty;
    public double Score { get; set; }
}
