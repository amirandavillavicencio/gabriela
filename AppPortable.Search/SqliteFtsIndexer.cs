using AppPortable.Application.Abstractions;
using AppPortable.Domain.Models;
using AppPortable.Infrastructure.Persistence;
using Microsoft.Data.Sqlite;

namespace AppPortable.Search;

public sealed class SqliteFtsIndexer(AppPaths paths) : IIndexer
{
    private string DbPath => Path.Combine(paths.Index, "indice_global.sqlite");

    public async Task IndexDocumentAsync(DocumentRecord document, CancellationToken cancellationToken = default)
    {
        paths.EnsureAll();
        await using var connection = new SqliteConnection($"Data Source={DbPath}");
        await connection.OpenAsync(cancellationToken);
        await InitAsync(connection, cancellationToken);

        var delete = connection.CreateCommand();
        delete.CommandText = "DELETE FROM chunk_store WHERE document_id = $doc; DELETE FROM chunks_fts WHERE document_id = $doc;";
        delete.Parameters.AddWithValue("$doc", document.DocumentId);
        await delete.ExecuteNonQueryAsync(cancellationToken);

        foreach (var chunk in document.Chunks)
        {
            await using var cmd = connection.CreateCommand();
            cmd.CommandText = @"INSERT INTO chunk_store (chunk_id, document_id, source_file, page_start, page_end, chunk_index, extraction_layers, avg_confidence, text)
VALUES ($chunk_id, $doc, $source, $start, $end, $index, $layers, $confidence, $text);
INSERT INTO chunks_fts (chunk_id, document_id, source_file, page_start, page_end, chunk_index, extraction_layers, avg_confidence, text)
VALUES ($chunk_id, $doc, $source, $start, $end, $index, $layers, $confidence, $text);";
            cmd.Parameters.AddWithValue("$chunk_id", chunk.ChunkId);
            cmd.Parameters.AddWithValue("$doc", chunk.DocumentId);
            cmd.Parameters.AddWithValue("$source", chunk.SourceFile);
            cmd.Parameters.AddWithValue("$start", chunk.PageStart);
            cmd.Parameters.AddWithValue("$end", chunk.PageEnd);
            cmd.Parameters.AddWithValue("$index", chunk.ChunkIndex);
            cmd.Parameters.AddWithValue("$layers", string.Join(',', chunk.ExtractionLayersInvolved));
            cmd.Parameters.AddWithValue("$confidence", (object?)chunk.AvgConfidence ?? DBNull.Value);
            cmd.Parameters.AddWithValue("$text", chunk.Text);
            await cmd.ExecuteNonQueryAsync(cancellationToken);
        }
    }

    public async Task<IReadOnlyList<SearchResultRecord>> SearchAsync(string query, int limit = 20, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        if (!File.Exists(DbPath)) return [];

        await using var connection = new SqliteConnection($"Data Source={DbPath}");
        await connection.OpenAsync(cancellationToken);
        var cmd = connection.CreateCommand();
        cmd.CommandText = @"SELECT chunk_id, document_id, source_file, page_start, page_end, chunk_index,
 bm25(chunks_fts) as score, snippet(chunks_fts, 8, '…', '…', '...', 24) as snippet
 FROM chunks_fts WHERE chunks_fts MATCH $query ORDER BY bm25(chunks_fts) LIMIT $limit;";
        cmd.Parameters.AddWithValue("$query", query.Trim());
        cmd.Parameters.AddWithValue("$limit", Math.Max(1, limit));

        var results = new List<SearchResultRecord>();
        await using var reader = await cmd.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            results.Add(new SearchResultRecord
            {
                ChunkId = reader.GetString(0),
                DocumentId = reader.GetString(1),
                SourceFile = reader.GetString(2),
                PageStart = reader.GetInt32(3),
                PageEnd = reader.GetInt32(4),
                ChunkIndex = reader.GetInt32(5),
                Score = reader.GetDouble(6),
                Snippet = reader.IsDBNull(7) ? string.Empty : reader.GetString(7)
            });
        }

        return results;
    }

    private static async Task InitAsync(SqliteConnection connection, CancellationToken cancellationToken)
    {
        var cmd = connection.CreateCommand();
        cmd.CommandText = @"
CREATE TABLE IF NOT EXISTS chunk_store (
chunk_id TEXT PRIMARY KEY,
document_id TEXT NOT NULL,
source_file TEXT NOT NULL,
page_start INTEGER NOT NULL,
page_end INTEGER NOT NULL,
chunk_index INTEGER,
extraction_layers TEXT,
avg_confidence REAL,
text TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
chunk_id UNINDEXED,
document_id UNINDEXED,
source_file UNINDEXED,
page_start UNINDEXED,
page_end UNINDEXED,
chunk_index UNINDEXED,
extraction_layers UNINDEXED,
avg_confidence UNINDEXED,
text,
tokenize='unicode61'
);";
        await cmd.ExecuteNonQueryAsync(cancellationToken);
    }
}
