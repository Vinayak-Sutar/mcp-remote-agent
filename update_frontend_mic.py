import re

with open('templates/index.html', 'r') as f:
    text = f.read()

# Replace the Speech Audio Recording section
old_code = r"""        // --- Speech Audio Recording ---
        const micBtn = document.getElementById('mic-btn');
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;

        micBtn.addEventListener('click', async () => {
            if (!isRecording) {
                // Start Recording
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                    audioChunks = [];
                    
                    mediaRecorder.ondataavailable = event => {
                        if (event.data.size > 0) audioChunks.push(event.data);
                    };
                    
                    mediaRecorder.onstop = () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                        console.log("Sending audio blob of size:", audioBlob.size);
                        socket.emit('speech_audio', audioBlob);
                        
                        // Stop tracks to release mic
                        stream.getTracks().forEach(track => track.stop());
                    };
                    
                    mediaRecorder.start(); alert('Recording started! Speak now.');
                    isRecording = true;
                    micBtn.style.background = 'rgba(255, 50, 50, 0.6)'; // visual recording indicator
                    if (navigator.vibrate) navigator.vibrate(50);
                } catch (err) {
                    console.error("Mic access denied or unavailable", err);
                    alert("Microphone access denied. Note: Safari/Chrome require HTTPS or localhost (not raw IP) for microphone access unless configured.");
                }
            } else {
                // Stop Recording
                mediaRecorder.stop(); alert('Recording stopped! Sending to server...');
                isRecording = false;
                micBtn.style.background = 'rgba(255, 50, 50, 0.15)'; // reset
                if (navigator.vibrate) navigator.vibrate(50);
            }
        });"""

new_code = r"""        // --- Speech Audio Recording ---
        const micBtn = document.getElementById('mic-btn');
        let mediaRecorder;
        let isRecording = false;
        let currentStream;
        let chunkTimer;

        // Set default mic color to red
        micBtn.style.background = 'rgba(255, 0, 0, 0.6)';

        micBtn.addEventListener('click', async () => {
            if (!isRecording) {
                // Start Recording
                try {
                    currentStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    isRecording = true;
                    micBtn.style.background = 'rgba(0, 255, 0, 0.6)'; // green when recording

                    const startChunkRecord = () => {
                        if (!isRecording) return;
                        mediaRecorder = new MediaRecorder(currentStream, { mimeType: 'audio/webm' });
                        let audioChunks = [];
                        
                        mediaRecorder.ondataavailable = event => {
                            if (event.data.size > 0) audioChunks.push(event.data);
                        };
                        
                        mediaRecorder.onstop = () => {
                            if (audioChunks.length > 0) {
                                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                                socket.emit('speech_audio', audioBlob);
                            }
                        };
                        
                        mediaRecorder.start();
                        
                        // Stop and restart every 3 seconds to send chunks
                        chunkTimer = setTimeout(() => {
                            if (mediaRecorder.state !== 'inactive') {
                                mediaRecorder.stop();
                            }
                            startChunkRecord(); // Next chunk
                        }, 2500);
                    };

                    startChunkRecord();
                    if (navigator.vibrate) navigator.vibrate(50);

                } catch (err) {
                    console.error("Mic access denied or unavailable", err);
                }
            } else {
                // Stop Recording
                isRecording = false;
                clearTimeout(chunkTimer);
                if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                }
                if (currentStream) {
                    currentStream.getTracks().forEach(track => track.stop());
                }
                micBtn.style.background = 'rgba(255, 0, 0, 0.6)'; // red when not recording
                if (navigator.vibrate) navigator.vibrate(50);
            }
        });"""

if old_code in text:
    with open('templates/index.html', 'w') as f:
        f.write(text.replace(old_code, new_code))
    print("Replaced chunk logic successfully")
else:
    print("Could not find old code block, maybe already modified?")
