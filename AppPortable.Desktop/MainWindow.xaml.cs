using System.Windows;
using AppPortable.Core.Services;
using AppPortable.Desktop.ViewModels;
using AppPortable.Infrastructure.Persistence;
using AppPortable.Infrastructure.Processing;
using AppPortable.Search;

namespace AppPortable.Desktop;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        var paths = new AppPaths();
        DataContext = new MainWindowViewModel(
            new DocumentPipelineService(
                new PdfPigTextExtractor(),
                new TesseractCliOcrEngine(Environment.GetEnvironmentVariable("TESSERACT_CMD"), Environment.GetEnvironmentVariable("TESSERACT_LANG") ?? "spa"),
                new SemanticChunker(),
                new JsonFileStore(paths),
                new SqliteFtsIndexer(paths)),
            paths);
    }
}
