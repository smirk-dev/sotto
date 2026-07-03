# Generate speech WAVs with Windows built-in SAPI TTS (free, offline) for accuracy/latency tests.
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$dir = Join-Path $PSScriptRoot "wav"
New-Item -ItemType Directory -Force $dir | Out-Null

$cases = @{
  "short"  = "This is a quick test of the dictation system on my Windows machine."
  "medium" = "Suryansh is testing a fully local dictation application. It should insert accurate text at the cursor, handle punctuation correctly, and finish transcribing in under two seconds after he stops speaking."
  "long"   = "The quick brown fox jumps over the lazy dog. I am dictating a longer paragraph to measure how the engine handles extended speech. The application records audio from the microphone, transcribes it locally using a neural network, and then types the result into whatever window currently has focus. Nothing ever leaves this computer, there is no subscription, and every component is open source and completely free of cost."
}
foreach ($k in $cases.Keys) {
  $path = Join-Path $dir "$k.wav"
  $synth.SetOutputToWaveFile($path, (New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)))
  $synth.Speak($cases[$k])
  $synth.SetOutputToNull()
  Write-Output "$k -> $path"
}
$synth.Dispose()
