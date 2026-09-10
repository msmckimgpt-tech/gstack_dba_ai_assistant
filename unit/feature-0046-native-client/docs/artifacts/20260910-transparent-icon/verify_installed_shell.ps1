param([string]$InstallRoot, [string]$OutputFile)
$ErrorActionPreference='Stop'
$wsh=New-Object -ComObject WScript.Shell
$shell=New-Object -ComObject Shell.Application
$name='DQA Nondisruptive Test'
$paths=@(
 (Join-Path ([Environment]::GetFolderPath('Programs')) "$name\$name.lnk"),
 (Join-Path ([Environment]::GetFolderPath('Desktop')) "$name.lnk"),
 (Join-Path ([Environment]::GetFolderPath('Startup')) "$name.lnk")
)
$result=@()
foreach($path in $paths) {
 if(-not(Test-Path -LiteralPath $path)){throw "Missing isolated shortcut: $path"}
 $link=$wsh.CreateShortcut($path)
 $item=$shell.NameSpace((Split-Path $path)).ParseName((Split-Path $path -Leaf))
 $appid=$item.ExtendedProperty('System.AppUserModel.ID')
 if($link.TargetPath -ne (Join-Path $InstallRoot 'DQALauncher.exe')){throw 'Wrong shortcut target'}
 if($link.IconLocation -ne ((Join-Path $InstallRoot 'dqa.ico')+',0')){throw "Wrong shortcut icon: $($link.IconLocation)"}
 if($appid -ne 'Masangsoft.DQA.Connect'){throw 'Wrong shortcut AppUserModelID'}
 $result+=@{path=$path;target=$link.TargetPath;icon=$link.IconLocation;appid=$appid}
}
$protocol=(Get-Item 'HKCU:\Software\Classes\dqa-nondisruptive-test\DefaultIcon').GetValue('')
if($protocol -ne ((Join-Path $InstallRoot 'dqa.ico')+',0')){throw 'Wrong protocol icon'}
$uninstall=Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{C6B2BAAF-CF2B-42EA-974A-0A0B00000001}_is1'
if($uninstall.DisplayIcon -ne (Join-Path $InstallRoot 'dqa.ico')){throw 'Wrong uninstall display icon'}
@{result='PASS';shortcuts=$result;protocol=$protocol;uninstall=$uninstall.DisplayIcon} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $OutputFile
