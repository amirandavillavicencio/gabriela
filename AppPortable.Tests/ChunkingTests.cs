using AppPortable.Core.Models;
using AppPortable.Infrastructure.Processing;

namespace AppPortable.Tests;

public class ChunkingTests
{
    [Fact]
    public void Chunker_Creates_BoundedChunks()
    {
        var doc = new DocumentRecord
        {
            DocumentId = "doc_test",
            SourceFile = "test.pdf",
            Pages =
            [
                new PageContent { PageNumber = 1, Text = new string('A', 700), ExtractionLayer = ExtractionLayer.Native },
                new PageContent { PageNumber = 2, Text = new string('B', 700), ExtractionLayer = ExtractionLayer.Ocr }
            ]
        };

        var chunker = new SemanticChunker();
        var chunks = chunker.CreateChunks(doc, 500, 1000, 100);

        Assert.NotEmpty(chunks);
        Assert.All(chunks, c => Assert.InRange(c.TextLength, 100, 1200));
    }
}
