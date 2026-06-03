using System;
using System.Diagnostics;
using System.IO;
using System.Net.Sockets;
using System.Threading;

public static class StartToolbox
{
    private const string PythonExe = @"C:\Users\melonedoe\miniconda3\python.exe";
    private const string Host = "127.0.0.1";
    private const int Port = 8765;

    public static void Main()
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string python = File.Exists(PythonExe) ? PythonExe : "python";
        string url = "http://" + Host + ":" + Port;

        if (!IsPortOpen(Host, Port))
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = python,
                Arguments = "-m uvicorn app:app --host " + Host + " --port " + Port,
                WorkingDirectory = baseDir,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            Process.Start(startInfo);

            for (int i = 0; i < 80; i++)
            {
                if (IsPortOpen(Host, Port))
                {
                    break;
                }
                Thread.Sleep(100);
            }
        }

        Process.Start(new ProcessStartInfo
        {
            FileName = url,
            UseShellExecute = true
        });
    }

    private static bool IsPortOpen(string host, int port)
    {
        try
        {
            using (var client = new TcpClient())
            {
                var result = client.BeginConnect(host, port, null, null);
                bool success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(250));
                if (!success)
                {
                    return false;
                }
                client.EndConnect(result);
                return true;
            }
        }
        catch
        {
            return false;
        }
    }
}
