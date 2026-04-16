!include "MUI2.nsh"

!define APP_NAME "Mobile Remote"
!define APP_EXE "mobile-typer.exe"
!ifndef APP_SOURCE_DIR
  !define APP_SOURCE_DIR "..\dist\windows\mobile-typer"
!endif
!ifndef OUT_FILE
  !define OUT_FILE "..\dist\windows\mobile-typer-win7-setup.exe"
!endif

Name "${APP_NAME}"
OutFile "${OUT_FILE}"
InstallDir "$LOCALAPPDATA\MobileTyper"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show

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
FunctionEnd

Section "Install"
  RMDir /r "$INSTDIR"
  CreateDirectory "$INSTDIR"
  SetOutPath "$INSTDIR"
  File /r "${APP_SOURCE_DIR}\*"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  ClearErrors
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\${APP_EXE}" 0
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\${APP_NAME}.lnk"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR"
SectionEnd
