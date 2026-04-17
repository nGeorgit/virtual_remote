Unicode false

!include "MUI2.nsh"
!include "LogicLib.nsh"

!define APP_NAME "Mobile Remote"
!define APP_EXE "mobile-typer.exe"
!define APP_DIR_NAME "MobileTyper"
!define FIREWALL_RULE_NAME "Mobile Remote"
!define UNINSTALL_REG_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_DIR_NAME}"
!ifndef APP_SOURCE_DIR
  !define APP_SOURCE_DIR "..\dist\windows\mobile-typer"
!endif
!ifndef OUT_FILE
  !define OUT_FILE "..\dist\windows\mobile-typer-win7-setup.exe"
!endif

Name "${APP_NAME}"
OutFile "${OUT_FILE}"
InstallDir "$LOCALAPPDATA\${APP_DIR_NAME}"
InstallDirRegKey HKCU "Software\${APP_DIR_NAME}" "InstallDir"
RequestExecutionLevel highest
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
BrandingText "Mobile Remote Windows 7 Installer"

Var AccountType
Var StartMenuShortcut
Var DesktopShortcut
Var FirewallResult

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  IfFileExists "${APP_SOURCE_DIR}\${APP_EXE}" +2 0
    MessageBox MB_ICONSTOP|MB_OK "Missing onedir payload: ${APP_SOURCE_DIR}\${APP_EXE}"
    Abort

  UserInfo::GetAccountType
  Pop $AccountType
FunctionEnd

Function RefreshShellIcons
  System::Call 'shell32::SHChangeNotify(i, i, p, p) v (0x08000000, 0, 0, 0)'
FunctionEnd

Function un.RefreshShellIcons
  System::Call 'shell32::SHChangeNotify(i, i, p, p) v (0x08000000, 0, 0, 0)'
FunctionEnd

Function AddFirewallRule
  StrCpy $FirewallResult ""
  ClearErrors
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${FIREWALL_RULE_NAME}" program="$INSTDIR\${APP_EXE}"'
  Pop $0

  ClearErrors
  nsExec::ExecToLog 'netsh advfirewall firewall add rule name="${FIREWALL_RULE_NAME}" dir=in action=allow program="$INSTDIR\${APP_EXE}" profile=private enable=yes'
  Pop $FirewallResult
FunctionEnd

Function un.RemoveFirewallRule
  ClearErrors
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${FIREWALL_RULE_NAME}" program="$INSTDIR\${APP_EXE}"'
  Pop $0
FunctionEnd

Section "Install"
  SetShellVarContext current

  StrCpy $StartMenuShortcut "$SMPROGRAMS\${APP_NAME}.lnk"
  StrCpy $DesktopShortcut "$DESKTOP\${APP_NAME}.lnk"

  RMDir /r "$INSTDIR"
  CreateDirectory "$INSTDIR"
  SetOutPath "$INSTDIR"
  File /r "${APP_SOURCE_DIR}\*"

  WriteRegStr HKCU "Software\${APP_DIR_NAME}" "InstallDir" "$INSTDIR"

  CreateShortcut "$StartMenuShortcut" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  ClearErrors
  CreateShortcut "$DesktopShortcut" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0

  WriteUninstaller "$INSTDIR\uninstall.exe"

  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "DisplayVersion" "win7"
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "Publisher" "Mobile Typer"
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "UninstallString" "$\"$INSTDIR\uninstall.exe$\""
  WriteRegStr HKCU "${UNINSTALL_REG_KEY}" "QuietUninstallString" "$\"$INSTDIR\uninstall.exe$\" /S"
  WriteRegDWORD HKCU "${UNINSTALL_REG_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_REG_KEY}" "NoRepair" 1

  ${If} $AccountType == "Admin"
    DetailPrint "Adding Windows Firewall rule for ${APP_NAME}."
    Call AddFirewallRule
    ${If} $FirewallResult == "0"
      DetailPrint "Windows Firewall rule added or updated."
    ${Else}
      DetailPrint "Windows Firewall rule was not added. netsh exit code: $FirewallResult"
    ${EndIf}
  ${Else}
    DetailPrint "Installer is not elevated. Skipping the optional Windows Firewall rule."
  ${EndIf}

  Call RefreshShellIcons
SectionEnd

Section "Uninstall"
  SetShellVarContext current

  StrCpy $StartMenuShortcut "$SMPROGRAMS\${APP_NAME}.lnk"
  StrCpy $DesktopShortcut "$DESKTOP\${APP_NAME}.lnk"

  ${If} $AccountType == "Admin"
    DetailPrint "Removing Windows Firewall rule for ${APP_NAME}."
    Call un.RemoveFirewallRule
  ${Else}
    DetailPrint "Uninstaller is not elevated. Any existing Windows Firewall rule was left in place."
  ${EndIf}

  Delete "$StartMenuShortcut"
  Delete "$DesktopShortcut"
  DeleteRegKey HKCU "${UNINSTALL_REG_KEY}"
  DeleteRegKey HKCU "Software\${APP_DIR_NAME}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR"

  Call un.RefreshShellIcons
SectionEnd
