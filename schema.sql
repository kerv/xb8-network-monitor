--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 15.13 (Debian 15.13-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: channel_codewords; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.channel_codewords (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    channel_id integer NOT NULL,
    correctable numeric,
    uncorrectable numeric
);


ALTER TABLE public.channel_codewords OWNER TO postgres;

--
-- Name: channel_codewords_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.channel_codewords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.channel_codewords_id_seq OWNER TO postgres;

--
-- Name: channel_codewords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.channel_codewords_id_seq OWNED BY public.channel_codewords.id;


--
-- Name: cmts_tests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cmts_tests (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    ping double precision,
    packet_loss double precision NOT NULL,
    status character varying(20) NOT NULL
);


ALTER TABLE public.cmts_tests OWNER TO postgres;

--
-- Name: cmts_tests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cmts_tests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.cmts_tests_id_seq OWNER TO postgres;

--
-- Name: cmts_tests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cmts_tests_id_seq OWNED BY public.cmts_tests.id;


--
-- Name: modem_signals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.modem_signals (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    downstream_avg_snr double precision,
    downstream_min_snr double precision,
    downstream_avg_power double precision,
    downstream_max_power double precision,
    upstream_avg_power double precision,
    correctable_codewords numeric,
    uncorrectable_codewords numeric,
    worst_channel_id integer,
    worst_channel_correctable numeric,
    worst_channel_uncorrectable numeric
);


ALTER TABLE public.modem_signals OWNER TO postgres;

--
-- Name: modem_signals_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.modem_signals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.modem_signals_id_seq OWNER TO postgres;

--
-- Name: modem_signals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.modem_signals_id_seq OWNED BY public.modem_signals.id;


--
-- Name: ping_tests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.ping_tests (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    ping double precision,
    packet_loss double precision NOT NULL,
    status character varying(20) NOT NULL
);


ALTER TABLE public.ping_tests OWNER TO postgres;

--
-- Name: ping_tests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.ping_tests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ping_tests_id_seq OWNER TO postgres;

--
-- Name: ping_tests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.ping_tests_id_seq OWNED BY public.ping_tests.id;


--
-- Name: speed_tests; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.speed_tests (
    id integer NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    download double precision NOT NULL,
    upload double precision NOT NULL
);


ALTER TABLE public.speed_tests OWNER TO postgres;

--
-- Name: speed_tests_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.speed_tests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.speed_tests_id_seq OWNER TO postgres;

--
-- Name: speed_tests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.speed_tests_id_seq OWNED BY public.speed_tests.id;


--
-- Name: channel_codewords id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channel_codewords ALTER COLUMN id SET DEFAULT nextval('public.channel_codewords_id_seq'::regclass);


--
-- Name: cmts_tests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cmts_tests ALTER COLUMN id SET DEFAULT nextval('public.cmts_tests_id_seq'::regclass);


--
-- Name: modem_signals id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modem_signals ALTER COLUMN id SET DEFAULT nextval('public.modem_signals_id_seq'::regclass);


--
-- Name: ping_tests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ping_tests ALTER COLUMN id SET DEFAULT nextval('public.ping_tests_id_seq'::regclass);


--
-- Name: speed_tests id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.speed_tests ALTER COLUMN id SET DEFAULT nextval('public.speed_tests_id_seq'::regclass);


--
-- Name: channel_codewords channel_codewords_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.channel_codewords
    ADD CONSTRAINT channel_codewords_pkey PRIMARY KEY (id);


--
-- Name: cmts_tests cmts_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cmts_tests
    ADD CONSTRAINT cmts_tests_pkey PRIMARY KEY (id);


--
-- Name: modem_signals modem_signals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.modem_signals
    ADD CONSTRAINT modem_signals_pkey PRIMARY KEY (id);


--
-- Name: ping_tests ping_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.ping_tests
    ADD CONSTRAINT ping_tests_pkey PRIMARY KEY (id);


--
-- Name: speed_tests speed_tests_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.speed_tests
    ADD CONSTRAINT speed_tests_pkey PRIMARY KEY (id);


--
-- Name: idx_channel_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_channel_id ON public.channel_codewords USING btree (channel_id);


--
-- Name: idx_channel_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_channel_timestamp ON public.channel_codewords USING btree ("timestamp");


--
-- Name: idx_cmts_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cmts_timestamp ON public.cmts_tests USING btree ("timestamp");


--
-- Name: idx_modem_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_modem_timestamp ON public.modem_signals USING btree ("timestamp");


--
-- Name: idx_ping_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ping_timestamp ON public.ping_tests USING btree ("timestamp");


--
-- Name: idx_speed_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_speed_timestamp ON public.speed_tests USING btree ("timestamp");


--
-- PostgreSQL database dump complete
--


-- Weather data table
CREATE TABLE IF NOT EXISTS weather_data (
    timestamp TIMESTAMP PRIMARY KEY,
    temperature REAL,
    precipitation REAL,
    weather_code INTEGER
);
