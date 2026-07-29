function [output] = objective2(x, t, C_plus, C_minus, C_0, chi_plus, chi_minus, B0)
%OBJECTIVE2 Summary of this function goes here
%   Detailed explanation goes here
R_star_2_0 = x;
output = log(signalModel(t,C_plus, C_minus, C_0, chi_plus, chi_minus, R_star_2_0, B0));

end
