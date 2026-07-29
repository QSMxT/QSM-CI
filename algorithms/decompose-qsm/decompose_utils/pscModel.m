function [output] = pscModel(t, C_plus, C_minus, C_0, chi_plus, chi_minus, R_star_2_0, B0)
%S Summary of this function goes here
%   Detailed explanation goes here                
gamma = 42.58 * 2*pi;
a = (2*pi*gamma*B0)/(9*sqrt(3));

term1  = C_plus  * exp(-( a*chi_plus +R_star_2_0+(1j*(2/3)* chi_plus *gamma*B0))*t);
term3  = (C_0 + C_minus)     * exp(-R_star_2_0*t);
output = term1 + term3;
end

