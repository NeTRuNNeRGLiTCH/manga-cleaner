@echo off
REM Builds the standalone TensorRT engine probe (tools/trt_probe/trt_probe.exe).
REM Usage: tools\trt_probe\build_probe.bat
setlocal
set TRT=C:\Program Files\NVIDIA\TensorRT-11.2.1.2
set CUDA=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3
set VCVARS=C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\Auxiliary\Build\vcvars64.bat

if not exist "%VCVARS%" (
  echo ERROR: vcvars64.bat not found at "%VCVARS%"
  exit /b 1
)

call "%VCVARS%" >nul 2>&1

cd /d "%~dp0..\.."
cl /nologo /std:c++17 /EHsc /O2 /DWIN32 /D_WINDOWS ^
  /I"%TRT%\include" ^
  /I"%CUDA%\include" ^
  tools\trt_probe\trt_probe.cpp ^
  /link /LIBPATH:"%TRT%\lib" nvinfer_11.lib ^
  /LIBPATH:"%CUDA%\lib\x64" cudart.lib ^
  /OUT:tools\trt_probe\trt_probe.exe

endlocal
REM NOTE: trt_probe.exe needs nvinfer_11.dll next to it (or on PATH):
REM   copy "C:\Program Files\NVIDIA\TensorRT-11.2.1.2\bin\nvinfer_11.dll" tools\trt_probe\
