# Independent exact comparison. Only base R is loaded by the Python launcher.
# No Python verdict, detector score, expected label or normalized row is read.

main <- function(directory) {
    options(warn = 2)
    Sys.setlocale("LC_COLLATE", "C")
    split <- function(line) strsplit(line, "\t", fixed = TRUE)[[1L]]
    expect <- function(condition) {
        if (!isTRUE(condition)) stop("invalid review transport", call. = FALSE)
    }
    integer_text <- function(value) {
        expect(grepl("^-?[0-9]+$", value))
        negative <- startsWith(value, "-")
        digits <- sub("^-", "", value)
        digits <- sub("^0+", "", digits)
        if (!nzchar(digits)) return("0")
        paste0(if (negative) "-" else "", digits)
    }
    # Arbitrary precision integer comparison uses decimal digits, never double.
    int_compare_canonical <- function(left, right) {
        a_negative <- startsWith(left, "-")
        b_negative <- startsWith(right, "-")
        if (a_negative != b_negative) return(if (a_negative) -1L else 1L)
        a <- sub("^-", "", left)
        b <- sub("^-", "", right)
        result <- if (nchar(a) != nchar(b)) sign(nchar(a) - nchar(b)) else {
            if (a == b) 0L else if (a < b) -1L else 1L
        }
        if (a_negative) -result else result
    }
    int_compare <- function(left, right) {
        int_compare_canonical(integer_text(left), integer_text(right))
    }
    twice <- function(value) {
        digits <- as.integer(strsplit(value, "", fixed = TRUE)[[1L]])
        carry <- 0L
        for (i in rev(seq_along(digits))) {
            number <- 2L * digits[i] + carry
            digits[i] <- number %% 10L
            carry <- number %/% 10L
        }
        paste0(if (carry) as.character(carry) else "", paste0(digits, collapse = ""))
    }
    subtract_one <- function(value) {
        digits <- as.integer(strsplit(value, "", fixed = TRUE)[[1L]])
        for (i in rev(seq_along(digits))) {
            if (digits[i] > 0L) {
                digits[i] <- digits[i] - 1L
                break
            }
            digits[i] <- 9L
        }
        integer_text(paste0(digits, collapse = ""))
    }
    power_two <- function(bits) {
        result <- "1"
        for (i in seq_len(bits)) result <- twice(result)
        result
    }
    decimal_parts <- function(value) {
        expect(grepl("^-?[0-9]+(\\.[0-9]+)?([Ee][+-]?[0-9]+)?$", value))
        exponent_parts <- strsplit(tolower(value), "e", fixed = TRUE)[[1L]]
        exponent <- if (length(exponent_parts) == 2L) as.integer(exponent_parts[2L]) else 0L
        expect(!is.na(exponent) && abs(exponent) <= 152L)
        negative <- startsWith(exponent_parts[1L], "-")
        body <- sub("^-", "", exponent_parts[1L])
        dot <- regexpr(".", body, fixed = TRUE)[1L]
        fraction <- if (dot < 0L) 0L else nchar(body) - dot
        digits <- gsub(".", "", body, fixed = TRUE)
        scale <- fraction - exponent
        if (scale < 0L) {
            digits <- paste0(digits, strrep("0", -scale))
            scale <- 0L
        }
        digits <- sub("^0+", "", digits)
        if (!nzchar(digits)) return(list(number = "0", scale = 0L))
        while (scale > 0L && endsWith(digits, "0")) {
            digits <- substr(digits, 1L, nchar(digits) - 1L)
            scale <- scale - 1L
        }
        list(number = paste0(if (negative) "-" else "", digits), scale = scale)
    }
    decimal_compare <- function(left, right) {
        a <- strsplit(left, ":", fixed = TRUE)[[1L]]
        b <- strsplit(right, ":", fixed = TRUE)[[1L]]
        a_scale <- as.integer(a[2L])
        b_scale <- as.integer(b[2L])
        int_compare(
            paste0(a[1L], strrep("0", max(0L, b_scale - a_scale))),
            paste0(b[1L], strrep("0", max(0L, a_scale - b_scale)))
        )
    }
    read_table <- function(path) {
        lines <- readLines(path, encoding = "ASCII", warn = TRUE)
        expect(length(lines) >= 2L && lines[1L] == "EFR_TABLE_1")
        dims <- as.integer(split(lines[2L]))
        expect(length(dims) == 2L && all(!is.na(dims)) && all(dims >= 0L))
        rows <- dims[1L]
        columns <- dims[2L]
        expect(columns > 0L && length(lines) == 2L + columns + rows)
        metadata <- lapply(lines[2L + seq_len(columns)], split)
        expect(all(lengths(metadata) == 2L))
        names <- vapply(metadata, `[[`, "", 1L)
        signatures <- vapply(metadata, `[[`, "", 2L)
        expect(!anyDuplicated(names))
        data <- if (rows) lapply(lines[2L + columns + seq_len(rows)], split) else list()
        expect(all(lengths(data) == columns))
        list(rows = rows, names = names, signatures = signatures, data = data)
    }

    config <- readLines(file.path(directory, "contract.txt"), encoding = "ASCII")
    expect(length(config) >= 5L && config[1L] == "EFR_CONTRACT_1")
    header <- split(config[2L])
    count <- as.integer(header[1L])
    expect(length(header) == 3L && !is.na(count) && count > 0L)
    expect(header[2L] %in% c("significant", "ignored"))
    expect(header[3L] %in% c("preserve", "distinct"))
    mode <- config[3L]
    expect(mode %in% c("sequence", "bag"))
    columns <- lapply(config[3L + seq_len(count)], split)
    expect(all(lengths(columns) == 4L))
    expected_names <- vapply(columns, `[[`, "", 1L)
    expected_types <- vapply(columns, `[[`, "", 2L)
    cursor <- 4L + count
    key_count <- as.integer(config[cursor])
    expect(!is.na(key_count) && key_count >= 0L)
    cursor <- cursor + 1L
    keys <- if (key_count) lapply(config[cursor - 1L + seq_len(key_count)], split) else list()
    expect(all(lengths(keys) == 3L))
    cursor <- cursor + key_count
    order_header <- split(config[cursor])
    sort_count <- as.integer(order_header[1L])
    expect(length(order_header) == 2L && !is.na(sort_count) && sort_count >= 0L)
    cursor <- cursor + 1L
    sorts <- if (sort_count) lapply(config[cursor - 1L + seq_len(sort_count)], split) else list()
    expect(all(lengths(sorts) == 3L) && length(config) == cursor - 1L + sort_count)
    expect((mode == "sequence") == (sort_count > 0L))

    violations <- 0L
    violate <- function() violations <<- violations + 1L
    # Bounds belong to the declared integer type, not to an individual cell.
    # Keep the original decimal-digit arithmetic and reuse its exact result.
    integer_ranges <- new.env(hash = TRUE, parent = emptyenv())
    integer_range <- function(bits, signed) {
        key <- paste0(bits, ":", as.integer(signed))
        if (!exists(key, envir = integer_ranges, inherits = FALSE)) {
            limit <- power_two(bits - as.integer(signed))
            assign(key, list(
                minimum = if (signed) paste0("-", limit) else "0",
                maximum = subtract_one(limit)
            ), envir = integer_ranges)
        }
        get(key, envir = integer_ranges, inherits = FALSE)
    }
    column_signatures <- lapply(columns, function(column) {
        strsplit(column[2L], ":", fixed = TRUE)[[1L]]
    })
    column_integer_ranges <- lapply(column_signatures, function(signature) {
        if (signature[1L] == "integer") {
            integer_range(as.integer(signature[2L]), signature[3L] == "1")
        } else NULL
    })
    normalize <- function(token, column, signature, bounds) {
        expect(nzchar(token))
        tag <- substr(token, 1L, 1L)
        value <- substring(token, 2L)
        if (tag == "N") {
            expect(token == "N")
            if (column[3L] == "0") violate()
            return(token)
        }
        kind <- signature[1L]
        if (kind == "boolean") {
            expect(token %in% c("B0", "B1"))
        } else if (kind == "string") {
            expect(tag == "S" && (value == "-" || grepl("^([0-9a-f]{2})+$", value)))
        } else if (kind == "integer") {
            expect(tag == "I")
            canonical <- integer_text(value)
            if (int_compare_canonical(canonical, bounds$minimum) < 0L ||
                int_compare_canonical(canonical, bounds$maximum) > 0L) violate()
            token <- paste0("I", canonical)
        } else if (kind == "decimal") {
            expect(tag == "D")
            parts <- decimal_parts(value)
            precision <- as.integer(signature[2L])
            scale <- as.integer(signature[3L])
            digits <- sub("^-", "", parts$number)
            if (parts$number != "0" &&
                (parts$scale > scale || nchar(digits) + scale - parts$scale > precision)) violate()
            token <- paste0("D", parts$number, ":", parts$scale)
        } else if (kind == "float") {
            expect(tag %in% c("F", "Q", "P", "M"))
            if (tag == "Q" && column[4L] == "forbid") violate()
            if (tag == "F") {
                number <- as.numeric(value)
                expect(is.finite(number))
                # R performs its own binary conversion; signed zero is equal.
                token <- paste0("F", if (number == 0) "0" else sprintf("%a", number))
            } else expect(nchar(token) == 1L)
        } else if (kind %in% c("date", "timestamp")) {
            expect(tag == if (kind == "date") "A" else "T")
            token <- paste0(tag, integer_text(value))
        } else stop("unsupported type", call. = FALSE)
        token
    }
    compare_cell <- function(a, b, sort_spec) {
        if (a == "N" || b == "N") {
            result <- as.integer(a == "N") - as.integer(b == "N")
            return(result * if (sort_spec[3L] == "first") -1L else 1L)
        }
        tag <- substr(a, 1L, 1L)
        other <- substr(b, 1L, 1L)
        if (tag %in% c("M", "F", "P", "Q")) {
            rank <- c(M = 0L, F = 1L, P = 2L, Q = 3L)
            result <- sign(rank[tag] - rank[other])
            if (!result && tag == "F") {
                result <- sign(as.numeric(substring(a, 2L)) - as.numeric(substring(b, 2L)))
            }
        } else if (tag %in% c("I", "A", "T")) {
            result <- int_compare_canonical(substring(a, 2L), substring(b, 2L))
        } else if (tag == "D") {
            result <- decimal_compare(substring(a, 2L), substring(b, 2L))
        } else {
            result <- if (a == b) 0L else if (a < b) -1L else 1L
        }
        result * if (sort_spec[2L] == "ascending") 1L else -1L
    }
    prepare <- function(table) {
        aligned <- match(expected_names, table$names)
        if (length(table$names) != count || anyNA(aligned) ||
            (header[2L] == "significant" && !identical(table$names, expected_names))) {
            violate()
            return(NULL)
        }
        if (!identical(unname(table$signatures[aligned]), unname(expected_types))) {
            violate()
            return(NULL)
        }
        result <- lapply(table$data, function(row) {
            vapply(seq_len(count), function(j) {
                normalize(row[aligned[j]], columns[[j]], column_signatures[[j]],
                          column_integer_ranges[[j]])
            }, "")
        })
        encoded <- vapply(result, paste, "", collapse = "\t")
        if (header[3L] == "distinct") violations <<- violations + sum(duplicated(encoded))
        for (key in keys) {
            indices <- as.integer(strsplit(key[3L], ",", fixed = TRUE)[[1L]])
            expect(all(!is.na(indices)) && all(indices >= 1L & indices <= count))
            key_rows <- lapply(result, `[`, indices)
            incomplete <- vapply(key_rows, function(values) any(values == "N"), FALSE)
            if (key[2L] == "reject") violations <<- violations + sum(incomplete)
            if (key[1L] == "1") {
                complete <- vapply(key_rows[!incomplete], paste, "", collapse = "\t")
                violations <<- violations + sum(duplicated(complete))
            }
        }
        if (length(result) > 1L && mode == "sequence") {
            for (i in 2L:length(result)) {
                comparison <- 0L
                for (sort_spec in sorts) {
                    j <- as.integer(sort_spec[1L])
                    expect(!is.na(j) && j >= 1L && j <= count)
                    comparison <- compare_cell(result[[i - 1L]][j], result[[i]][j], sort_spec)
                    if (comparison) break
                }
                if (comparison > 0L || (comparison == 0L && order_header[2L] == "reject")) violate()
            }
        }
        if (mode == "bag") sort(encoded, method = "radix") else encoded
    }
    left <- read_table(file.path(directory, "left.txt"))
    right <- read_table(file.path(directory, "right.txt"))
    a <- prepare(left)
    b <- prepare(right)
    matched <- 0L
    if (!is.null(a) && !is.null(b)) {
        if (mode == "sequence") {
            n <- min(length(a), length(b))
            if (n) matched <- sum(a[seq_len(n)] == b[seq_len(n)])
        } else {
            i <- 1L
            j <- 1L
            while (i <= length(a) && j <= length(b)) {
                if (a[i] == b[j]) {
                    matched <- matched + 1L
                    i <- i + 1L
                    j <- j + 1L
                } else if (a[i] < b[j]) i <- i + 1L else j <- j + 1L
            }
        }
    }
    unmatched <- left$rows + right$rows - 2L * matched
    state <- if (unmatched || violations) "different" else "equivalent"
    version <- paste(sprintf("%02x", as.integer(charToRaw(R.version.string))), collapse = "")
    writeLines(c("EFR_RESULT_1", state, as.character(matched), as.character(unmatched),
                 as.character(violations), as.character(left$rows), as.character(right$rows),
                 version), file.path(directory, "result.txt"), useBytes = TRUE)
}

arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) != 1L) quit(status = 2L)
tryCatch(main(arguments[1L]), error = function(error) {
    # No row values or paths are printed by the process error channel.
    writeLines("equiframe independent R review failed", stderr())
    quit(status = 3L)
})
