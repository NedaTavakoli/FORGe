#! /usr/bin/env python2.7

import variant
import logging
from collections import defaultdict

"""
I/O support functions
"""


def read_genome(filename, target_chrom=None):
    G = dict()
    seq = []
    skip = False

    with open(filename, 'r') as f:
        for line in f:
            # Skip header line
            if line[0] == '>':
                if not skip and len(seq) > 0:
                    G[chrom] = ''.join(seq)
                chrom = line.rstrip().split(' ')[0][1:]
                seq = []
                if target_chrom and not chrom == target_chrom:
                    skip = True
                else:
                    skip = False
                continue

            if not skip:
                seq.append(line.rstrip())
    if not skip and len(seq) > 0:
        G[chrom] = ''.join(seq)

    return G


def parse_1ksnp(filename, G=None, target_chrom=None):
    """
        filename: Path to 1ksnp file containing variant information
        G: Genome sequence. If present, count variants inconsistent with G

        Chromosome-name-keyed dictionary of VariantSet objects
    """

    # Variant list
    vardict = defaultdict(variant.VariantSet)

    if target_chrom is not None:
        target_chrom += '\t'

    n_var, n_target, n_nontarget = 0, 0, 0
    curr_name, curr_chr = None, None
    curr_nalt = 0
    wrong_count = 0

    with open(filename, 'r') as f:
        for line in f:
            if target_chrom is not None:
                if not line.startswith(target_chrom):
                    n_nontarget += 1
                    continue
                else:
                    n_target += 1
            row = line.split('\t')

            if curr_nalt == 0:
                if curr_chr is not None and row[0] != curr_chr:
                    logging.info('  Starting chromosome %s; %d variants so far' % (curr_chr, n_var))
                curr_pos = int(row[1])-1
                curr_orig = row[2]
                curr_chr = row[0]
                vardict[curr_chr].add_var(curr_pos, curr_orig, row[3], float(row[4]))
                n_var += 1
                curr_name = row[7]
                curr_nalt = 1
                if G and not G[curr_chr][curr_pos:curr_pos + len(curr_orig)] == curr_orig:
                    wrong_count += 1
            else:
                if row[7] != curr_name:
                    raise RuntimeError("Couldn't find all alternate alleles for variant " + curr_name)
                vardict[curr_chr].add_alt_to_last(row[3], float(row[4]))
                curr_nalt += 1

            if curr_nalt == int(row[6]):
                curr_var, curr_name = None, None
                curr_nalt = 0

    logging.info('Parsed %d variants from %d chromosomes' % (n_var, len(vardict)))

    if G and wrong_count > 0:
        print('%d / %d variants are inconsistent with the reference genome!' % (wrong_count, n_var))
        exit()

    return vardict


def write_vars(variants, locs, outfile):
    f_out = open(outfile, 'w')

    last_loc = None
    unique_count = 0

    curr_id = 0
    num_alts = 0
    count_added = 0
    num_target = len(locs)
    with open(variants, 'r') as f:
        for line in f:
            row = line.rstrip().split('\t')
            loc = int(row[1])

            while curr_id < num_target and loc > locs[curr_id]:
                curr_id += 1
                num_alts = 0

            if curr_id == num_target:
                break

            if loc == locs[curr_id]:
                # Convert location from 1-indexed to 0-indexed
                f_out.write(row[7] + '.' + str(num_alts) + '\tsingle\t' + row[0] + '\t' + str(loc-1) + '\t' + row[3] + '\n')
                if not loc == last_loc:
                    unique_count += 1
                last_loc = loc
                num_alts += 1

    f_out.close()
    print('Found %d / %d target vars' % (unique_count, num_target))

# BTL: This won't work since I got rid of Variant.name field
"""
def write_pcs_subset(variants, seen_vars, pcs, prefix):
    with open(prefix + '.snp', 'w') as f_var:
        for i in range(len(variants)):
            v = variants[i]
            num_alts = sum(seen_vars[i])
            alt_id = 0
            for j in range(len(seen_vars[i])):
                if seen_vars[i][j]:
                    f_var.write(v.name + '.' + str(alt_id) + '\tsingle\t' + v.chrom + '\t' + str(v.pos) + '\t' + v.alts[j] + '\n')

                    # Replace presence boolean in variant list with alt allele id in file
                    seen_vars[i][j] = alt_id

                    alt_id += 1
                else:
                    seen_vars[i][j] = -1

    with open(prefix + '.haplotype', 'w') as f_pc:
        pc_id = 0
        for pc in pcs:
            i = pc[0]
            vec = pc[1]

            start = variants[i].pos
            end = start
            if seen_vars[i][vec[0]-1] < 0:
                print('Error! Alternate allele should not be present')
                exit()
            names = variants[i].name + '.' + str(seen_vars[i][vec[0]-1])
            for j in range(1, len(vec)):
                if vec[j] > 0:
                    end = variants[j].pos
                    if seen_vars[i+j][vec[j]-1]:
                        print('Error! Alternate allele should not be present')
                        exit()
                    names = names + ',' + variants[j].name + '.' + str(seen_vars[i+j][vec[j]-1])

            out_row = ['ht'+str(pc_id), variants[i].chrom, str(start), str(end), names]
            f_pc.write('\t'.join(out_row) + '\n')
            pc_id += 1

def write_pcs(variants, pcs, prefix):
    with open(prefix + '.snp', 'w') as f_var:
        for i in range(len(variants)):
            v = variants[i]
            for j in range(v.num_alts):
                f_var.write(v.name + '.' + str(j) + '\tsingle\t' + v.chrom + '\t' + str(v.pos) + '\t' + v.alts[j] + '\n')

    with open(prefix + '.haplotype', 'w') as f_pc:
        pc_id = 0
        for pc in pcs:
            i = pc[0]
            vec = pc[1]

            start = variants[i].pos
            end = start
            names = variants[i].name + '.' + str(vec[0]-1)
            for j in range(1, len(vec)):
                if vec[j] > 0:
                    end = variants[i+j].pos
                    names = names + ',' + variants[i+j].name + '.' + str(vec[j]-1)

            out_row = ['ht'+str(pc_id), variants[i].chrom, str(start), str(end), names]
            f_pc.write('\t'.join(out_row) + '\n')
            pc_id += 1
"""

class HaplotypeParser:

    def __init__(self, filename):
        self.filename = filename
        self.indiv_chunk_start = 0
        self.indiv_chunk_end = 0
        self.numH = 0
        self.indiv_chunk_size = 100000
        self.chunk_offset = 0 # location in file to seek for start of next chunk

    def get_ref_freq(self, var_ids, counts):
        '''
            Return the frequency for the reference haplotype overlapping the given alleles
        '''
        
        if (not self.indiv_chunk_end) or (var_ids[-1] >= self.indiv_chunk_end):
            self.read_next_chunk(var_ids[0], var_ids[-1])

        num_vecs = 1
        for c in counts:
            num_vecs *= (c+1)

        # Plus-one smooth
        ref_count = 1
        total_count = min(num_vecs, 256) # Limit on plus-one smoothing for large blowup regions

        for i in range(self.numH):
            total_count += 1
            if all(self.haplotypes[j-self.indiv_chunk_start][i] == 0 for j in var_ids):
                ref_count += 1
        return float(ref_count) / total_count 

    def get_seen_pcs(self, var_ids, counts):
        # Return all combinations of alleles that appear in each one individual, where first variant is always alt
        if (not self.indiv_chunk_end) or (var_ids[-1] >= self.indiv_chunk_end):
            self.read_next_chunk(var_ids[0], var_ids[-1])

        alleles = dict()
        for i in range(self.numH):
            v = [self.haplotypes[j-self.indiv_chunk_start][i] for j in var_ids]
            if v[0] > 0:
                id = self.vec_to_id(v, counts)
                if id in alleles:
                    alleles[id] += 1
                else:
                    alleles[id] = 1

        return [(self.id_to_vec(a, counts), float(c)/self.numH) for a,c in alleles.items()]

    def get_freqs(self, var_ids, counts):
        '''
            Return an array containing the smoothed frequency for each combination of alleles among the SNPs given
        '''

        if (not self.indiv_chunk_end) or (var_ids[-1] >= self.indiv_chunk_end):
            self.read_next_chunk(var_ids[0], var_ids[-1])

        if var_ids[0] < self.indiv_chunk_start:
            print('Error! Variant id earlier than contained in the current chunk')

        num_vecs = 1
        for c in counts:
            num_vecs *= (c+1)

        total = num_vecs
        good_turing = False
        if len(var_ids) > 8:
            # Good Turing smoothing
            good_turing = True
            allele_counts = [0] * num_vecs
        elif len(var_ids) > 1:
            # Plus 1 smoothing
            total = num_vecs + self.numH
            allele_counts = [1] * num_vecs
        else:
            # No smoothing
            total = self.numH
            allele_counts = [0] * num_vecs

        for i in range(self.numH):
            v = [self.haplotypes[j-self.indiv_chunk_start][i] for j in var_ids]
            allele_counts[self.vec_to_id(v, counts)] += 1

        if good_turing:
            freqs = [0] * (max(allele_counts)+1)
            for c in allele_counts:
                freqs[c] += 1

            smoothed_probs = self.good_turing_smoothing(freqs)
            allele_counts = [smoothed_probs[a] for a in allele_counts]
        else:
            allele_counts = [float(a) / total for a in allele_counts]

        return allele_counts

    def read_next_chunk(self, min_snp, max_snp):
        '''
            min_snp, max_snp: Line ids in the file of the first and last SNPs in the current window
        '''

        if max_snp >= self.indiv_chunk_end + self.indiv_chunk_size:
            print('Error! Chunk size is not large enough to hold all SNPs in window! Try increasing indiv_chunk_size')
            exit()

        with open(self.filename, 'r') as f:
            if min_snp < self.indiv_chunk_end:
                prev_lines = self.indiv_chunk_end - min_snp
                prev_chunk_start = len(self.haplotypes) - prev_lines
            else:
                prev_lines = 0

            if not self.numH:
                self.numH = len(f.readline().rstrip().split(','))

            f.seek(self.chunk_offset)
            haplotypes = [0] * (prev_lines + self.indiv_chunk_size)
            for i in range(prev_lines):
                haplotypes[i] = self.haplotypes[prev_chunk_start + i]
            for i in range(prev_lines, prev_lines+self.indiv_chunk_size):
                line = f.readline()
                if line:
                    haplotypes[i] = [int(allele) for allele in line.rstrip().split(',')]
                else:
                    break

            self.chunk_offset = f.tell()
            self.indiv_chunk_start = min(min_snp, self.indiv_chunk_end)
            self.indiv_chunk_end += self.indiv_chunk_size
            self.haplotypes = haplotypes

    def read_full_haps(self, num_v):
        haps = []
        with open(self.filename, 'r') as f:
            numH = len(f.readline().rstrip().split(','))
            self.numH = numH
            f.seek(0)
            for _ in range(self.numH):
                haps.append([0] * num_v)

            line_id = 0
            for line in f:
                print('Reading line %d / %d' % (line_id+1, num_v))
                row = line.rstrip().split(',')
                for i in range(numH):
                    haps[i][line_id] = int(row[i])
                line_id += 1
            if not line_id == num_v:
                print('Warning: Looking for %d variants, only %d lines in phasing file!' % (num_v, line_id))
        return haps

    def reset_chunk(self):
        self.indiv_chunk_start = 0
        self.indiv_chunk_end = 0
        self.chunk_offset = 0

    def good_turing_smoothing(self, counts):
        '''
            counts: a list of count frequencies, i.e. counts[i] is the number of haplotypes with frequency i
            return: a list p of probabilities such that p[i] is the new probability for haplotypes with frequency i
        '''

        max_c = len(counts)
        adj_counts = [0.0] * max_c
        total_weight = 0.0
        for i in range(max_c-1):
            # No haplotypes with this frequency, so no need to compute probability
            if counts[i] == 0:
                continue

            next_count = counts[i+1]
            if next_count == 0:
                for j in range(i+1, max_c):
                    if counts[j] > 0:
                        break
                if counts[j] > 0:
                    next_count = counts[i] + float(counts[j] - counts[i]) / (j - i)
                else:
                    # No haplotypes with greater frequency
                    next_count = counts[i]

            adj_counts[i] = (i+1) * float(next_count) / counts[i]
            total_weight += (i+1) * float(next_count)

        # Last frequency
        adj_counts[-1] = i
        total_weight += i * counts[-1]

        return [i / total_weight for i in adj_counts]

    def vec_to_id(self, v, counts):
        id = 0
        for i in range(len(v)):
            if v[i] > counts[i]:
                print('Error in allele vector! Vector is ' + str(v) + ' but counts are ' + str(counts))
                traceback.print_stack()
                exit()

            id = id * (counts[i]+1) + v[i]

        return id

    def id_to_vec(self, id, counts):
        v = [0] * len(counts)
        for i in range(len(counts)-1, 0, -1):
            v[i] = id % (counts[i]+1)
            id = (id - v[i]) / (counts[i]+1)
        v[0] = id
        return v