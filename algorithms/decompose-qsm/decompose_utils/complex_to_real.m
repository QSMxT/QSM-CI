function y_real = complex_to_real(y)
y_real = [real(y(:)); -imag(y(:))];
end