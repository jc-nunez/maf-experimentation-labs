using System.ClientModel.Primitives;
using System.Text;
using System.Text.RegularExpressions;

namespace MafLabs.Hosting;

/// <summary>
/// SGLang sends Responses timestamps as floats (<c>"created_at": 1791565580.0</c>); the OpenAI .NET SDK reads them
/// as integers and throws <see cref="FormatException"/>. This policy rewrites them to integers while the response
/// streams. The python SDK tolerates floats, so only the .NET host needs it.
/// </summary>
internal sealed partial class SglangCompatPolicy : PipelinePolicy
{
    [GeneratedRegex(@"(""(?:created_at|completed_at)""\s*:\s*)(\d+)\.\d+")]
    private static partial Regex FloatTimestamp();

    public override void Process(PipelineMessage message, IReadOnlyList<PipelinePolicy> pipeline, int currentIndex)
    {
        ProcessNext(message, pipeline, currentIndex);
        Rewrite(message);
    }

    public override async ValueTask ProcessAsync(PipelineMessage message, IReadOnlyList<PipelinePolicy> pipeline, int currentIndex)
    {
        await ProcessNextAsync(message, pipeline, currentIndex).ConfigureAwait(false);
        Rewrite(message);
    }

    private static void Rewrite(PipelineMessage message)
    {
        if (message.Response?.ContentStream is { } stream)
        {
            message.Response.ContentStream = new LineRewriteStream(stream, line => FloatTimestamp().Replace(line, "$1$2"));
        }
    }

    /// <summary>Read-only stream that applies a rewrite to each line as it is read (keeps SSE streaming).</summary>
    private sealed class LineRewriteStream(Stream inner, Func<string, string> rewrite) : Stream
    {
        private readonly StreamReader _reader = new(inner, Encoding.UTF8);
        private byte[] _buffer = [];
        private int _position;

        public override async ValueTask<int> ReadAsync(Memory<byte> destination, CancellationToken cancellationToken = default)
        {
            while (_position >= _buffer.Length)
            {
                var line = await _reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
                if (line is null) return 0;
                _buffer = Encoding.UTF8.GetBytes(rewrite(line) + "\n");
                _position = 0;
            }
            var count = Math.Min(destination.Length, _buffer.Length - _position);
            _buffer.AsMemory(_position, count).CopyTo(destination);
            _position += count;
            return count;
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();

        public override int Read(byte[] buffer, int offset, int count) =>
            ReadAsync(buffer.AsMemory(offset, count)).AsTask().GetAwaiter().GetResult();

        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        protected override void Dispose(bool disposing)
        {
            if (disposing) _reader.Dispose();
            base.Dispose(disposing);
        }
    }
}
