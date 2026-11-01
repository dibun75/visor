using System;
using System.Collections.Generic;
using Alias = Demo.Lib;
using static System.Math;

namespace Demo.App
{
    public interface IWorker
    {
        void Run();
    }

    public struct Point
    {
        public int X;
    }

    public record Person(string Name);

    public enum Color
    {
        Red,
        Green,
    }

    public class Service : IWorker
    {
        public Service()
        {
            Helper();
        }

        public void Run()
        {
            this.Go();
            worker.Run();
            Console.WriteLine("ready");
        }

        private void Go()
        {
        }

        private static void Helper()
        {
        }
    }
}
