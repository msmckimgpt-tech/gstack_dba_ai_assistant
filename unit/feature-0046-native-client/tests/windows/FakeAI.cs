using System;
using System.IO;
using System.Text;
class FakeAI {
 static void Main(string[] args) {
  string cmd=string.Join(" ",args);
  string name=Path.GetFileNameWithoutExtension(System.Reflection.Assembly.GetExecutingAssembly().Location);
  if(name=="wsl") {
   if(cmd.Contains("-l -q")) {Console.OutputEncoding=Encoding.Unicode;Console.WriteLine("FixtureUbuntu");return;}
   if(cmd.Contains("getent passwd")){Console.WriteLine("alice:x:1000:1000::/home/alice:/bin/bash");return;}
   if(cmd.Contains("command -v")){Console.WriteLine("claude\t/home/alice/bin/claude");return;}
   name="claude";
  }
  Console.OutputEncoding=new UTF8Encoding(false);
  if(cmd.Contains("auth status")){Console.WriteLine("{\"loggedIn\":true}");return;}
  if(cmd.Contains("login status")){Console.WriteLine("Logged in using ChatGPT");return;}
  if(cmd.Contains("--help")){Console.WriteLine("--strict-mcp-config --append-system-prompt --model --effort");return;}
  if(cmd.Contains("--version")){Console.WriteLine("1.0.0 fixture");return;}
  Console.WriteLine("{\"label\":\"Fixture AI\",\"models\":[{\"value\":\"fixture-model\",\"label\":\"Fixture model\"}],\"efforts\":[],\"model_flag\":[\"--model\",\"{model}\"],\"effort_flag\":[]}");
 }
}
