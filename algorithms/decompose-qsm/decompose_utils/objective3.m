function [output] = objective3(x, t, C_plus, C_minus, C_0, R_star_2_0, B0)
%OBJECTIVE3 Summary of this function goes here
%   Detailed explanation goes here
chi_plus  = x(1);
chi_minus = x(2);
output = log(signalModel(t,C_plus, C_minus, C_0, chi_plus, chi_minus, R_star_2_0, B0));


end


