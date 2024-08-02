const audioPlayer = document.getElementById('audio-player');
const source = document.getElementById('audio-source');

// Setup the audio player controls
const playPause = document.getElementById('play-pause');
const next = document.getElementById('next');
const previous = document.getElementById('previous');
const seekBar = document.getElementById('seek-bar');
const currentTime = document.getElementById('current-time');
const duration = document.getElementById('duration');


// Hide the default audio player
audioPlayer.style.display = 'none';

function playTrack(file) {
  source.src = file;
  audioPlayer.load();
  audioPlayer.play();
}

const trackListing = document.getElementById('track-list');
// Add click event listener to each track
for (const track of trackListing.children) {
  track.onclick = function () {
    for (const _track of trackListing.children) {
      _track.classList.remove('active');
    }
    track.classList.add('active');
    const file = track.getAttribute('data-src');
    playTrack(file);
    // Change the play button to pause
    playPause.textContent = 'Pause';
  };
}

// Add listener to the audio player to play the next track
audioPlayer.addEventListener('ended', function () {
  const nextTrack = document.querySelector('.active').nextElementSibling;
  if (nextTrack) {
    nextTrack.click();
  } else {
    playPause.textContent = 'Play';
  }
});


// Add listeners
playPause.onclick = function () {
  if (audioPlayer.paused) {
    audioPlayer.play();
    playPause.textContent = 'Pause';
  } else {
    audioPlayer.pause();
    playPause.textContent = 'Play';
  }
};

next.onclick = function () {
  const nextTrack = document.querySelector('.active').nextElementSibling;
  if (nextTrack) {
    nextTrack.click();
  }
};

previous.onclick = function () {
  const previousTrack = document.querySelector('.active').previousElementSibling;
  if (previousTrack) {
    previousTrack.click();
  }
};

seekBar.oninput = function () {
  const seekTime = audioPlayer.duration * (seekBar.value / 100);
  audioPlayer.currentTime = seekTime;
};

// Update the seek bar as the audio plays
audioPlayer.ontimeupdate = function () {
  // If metadata is loaded, set the duration
  if (audioPlayer.duration) {
    const currentTimeValue = audioPlayer.currentTime;
    const durationValue = audioPlayer.duration;
    const seekValue = (currentTimeValue / durationValue) * 100;
    seekBar.value = seekValue;
    currentTime.textContent = formatTime(currentTimeValue);
    duration.textContent = formatTime(durationValue);
  }
};

function formatTime(time) {
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
}
