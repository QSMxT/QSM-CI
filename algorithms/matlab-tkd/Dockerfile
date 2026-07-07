# MATLAB submission image — compiled code on the license-free MATLAB Runtime.
# The `recon` binary is produced on a machine with MATLAB + MATLAB Compiler (see BUILD.md), then
# baked onto the MATLAB Runtime base (matching the compiler version). No MATLAB license at run time.
FROM containers.mathworks.com/matlab-runtime:r2023b
COPY recon run.sh /opt/algo/
WORKDIR /opt/algo
RUN chmod +x /opt/algo/run.sh /opt/algo/recon
