function currentNbaSeasonStartYear() {
  const now = new Date();
  if (now.getMonth() > 9 || (now.getMonth() === 9 && now.getDate() >= 15)) {
    return now.getFullYear();
  }
  return now.getFullYear() - 1;
}

function toSeasonLabel(startYear) {
  const endYY = String((startYear + 1) % 100).padStart(2, '0');
  return `${startYear}-${endYY}`;
}

console.log('Current date:', new Date());
console.log('Frontend current season:', toSeasonLabel(currentNbaSeasonStartYear()));
