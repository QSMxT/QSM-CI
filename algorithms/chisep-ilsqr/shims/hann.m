function w = hann(N)
    w = 0.5*(1 - cos(2*pi*(0:N-1)'/(N-1)));
end
